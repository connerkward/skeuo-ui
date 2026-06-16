#!/usr/bin/env python3
"""Convert an API-format ComfyUI workflow (what run.py POSTs) into UI-GRAPH
format (nodes/links/positions) so it opens normally from the Desktop app's
workflow sidebar — not just via drag-drop. Uses the live server's /object_info
to classify each input as widget vs connection and to order widgets_values
exactly as the frontend expects (incl. control_after_generate seed pairs).

Usage: python3 to_ui.py <api_workflow.json> [out.json]
"""
import json, os, sys, urllib.request

SERVER = os.environ.get("COMFY_SERVER", "127.0.0.1:8188")
WIDGET_PRIMS = {"INT", "FLOAT", "STRING", "BOOLEAN"}


def object_info():
    with urllib.request.urlopen(f"http://{SERVER}/object_info", timeout=30) as r:
        return json.load(r)


def is_widget(spec):
    """spec = [type, opts]. COMBO (list options or 'COMBO') and primitive
    scalars are widgets; everything else is a connection (link) input."""
    t = spec[0]
    if isinstance(t, list):
        return True            # inline COMBO
    if t == "COMBO":
        return True            # API-node COMBO
    return t in WIDGET_PRIMS


def conn_type(spec):
    t = spec[0]
    return "COMBO" if isinstance(t, list) else t


def ordered_inputs(oi_node):
    inp = oi_node["input"]
    out = []
    for sec in ("required", "optional"):
        for k, v in inp.get(sec, {}).items():
            out.append((k, v))
    return out


def default_of(spec):
    if isinstance(spec[0], list):
        return spec[0][0] if spec[0] else ""
    o = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
    if "default" in o:
        return o["default"]
    return {"INT": 0, "FLOAT": 0.0, "STRING": "", "BOOLEAN": False}.get(spec[0], None)


def convert(api, oi):
    prompt = api["prompt"] if "prompt" in api else api
    nodes, links = [], []
    link_id = 0
    # stable integer ids
    id_map = {sid: int(sid) if str(sid).isdigit() else (i + 1)
              for i, sid in enumerate(prompt)}
    # first pass: compute per-node widget/link layout
    layout = {}
    for sid, node in prompt.items():
        ct = node["class_type"]
        oin = oi[ct]
        oinputs = ordered_inputs(oin)
        widgets, conns = [], []     # conns: (name, type)
        wvals = []
        for name, spec in oinputs:
            if is_widget(spec):
                val = node["inputs"].get(name, default_of(spec))
                # don't emit a widget value for an input that is actually linked
                if isinstance(val, list) and len(val) == 2:
                    conns.append((name, conn_type(spec)))
                    continue
                wvals.append(val)
                opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                if opts.get("control_after_generate"):
                    wvals.append("fixed")
            else:
                conns.append((name, conn_type(spec)))
        if ct == "LoadImage":
            wvals = wvals + ["image"]   # upload control widget
        outs = list(zip(oin.get("output_name", oin.get("output", [])),
                        oin.get("output", [])))
        layout[sid] = {"conns": conns, "wvals": wvals, "outs": outs, "ct": ct}

    # second pass: build links from connection inputs
    out_links = {}   # (sid, slot) -> [link_ids]
    in_links = {}    # (sid, conn_index) -> link_id
    for sid, node in prompt.items():
        conns = layout[sid]["conns"]
        for ci, (name, ctype) in enumerate(conns):
            v = node["inputs"].get(name)
            if isinstance(v, list) and len(v) == 2:
                src_sid, src_slot = str(v[0]), v[1]
                link_id += 1
                links.append([link_id, id_map[src_sid], src_slot,
                              id_map[sid], ci, ctype])
                in_links[(sid, ci)] = link_id
                out_links.setdefault((src_sid, src_slot), []).append(link_id)

    # third pass: depth for x-layout
    def depth(sid, seen=None):
        seen = seen or set()
        if sid in seen:
            return 0
        seen = seen | {sid}
        ds = [0]
        for name in prompt[sid]["inputs"].values():
            if isinstance(name, list) and len(name) == 2:
                ds.append(1 + depth(str(name[0]), seen))
        return max(ds)
    col_count = {}
    for sid in prompt:
        node = prompt[sid]
        L = layout[sid]
        d = depth(sid)
        row = col_count.get(d, 0)
        col_count[d] = row + 1
        node_inputs = [{"name": n, "type": t, "link": in_links.get((sid, ci))}
                       for ci, (n, t) in enumerate(L["conns"])]
        node_outputs = [{"name": on, "type": ot,
                         "links": out_links.get((sid, si)) or None}
                        for si, (on, ot) in enumerate(L["outs"])]
        nodes.append({
            "id": id_map[sid], "type": L["ct"],
            "pos": [d * 360 + 40, row * 240 + 40],
            "size": [300, 200], "flags": {}, "order": id_map[sid], "mode": 0,
            "inputs": node_inputs, "outputs": node_outputs,
            "properties": {"Node name for S&R": L["ct"]},
            "widgets_values": L["wvals"],
        })
    nodes.sort(key=lambda n: n["id"])
    return {
        "id": "", "revision": 0,
        "last_node_id": max(id_map.values()),
        "last_link_id": link_id,
        "nodes": nodes, "links": links, "groups": [],
        "config": {}, "extra": {}, "version": 0.4,
    }


if __name__ == "__main__":
    api = json.load(open(sys.argv[1]))
    ui = convert(api, object_info())
    out = sys.argv[2] if len(sys.argv) > 2 else \
        sys.argv[1].replace(".json", "_ui.json")
    json.dump(ui, open(out, "w"), indent=2)
    print(f"wrote {out}: {len(ui['nodes'])} nodes, {len(ui['links'])} links")
