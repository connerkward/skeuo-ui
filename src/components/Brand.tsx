import "./Brand.css";

// The skeuo.fm wordmark: the favicon logomark + "skeuo" with a green ".fm" tld,
// reused across every surface (app sidebar, widget, exports) for one brand.
export function Brand({ size = "md", className = "" }: { size?: "sm" | "md"; className?: string }) {
  return (
    <span className={`brand brand-${size} ${className}`}>
      <img className="brand-ico" src="/favicon.svg" alt="" width={24} height={24} />
      <span className="brand-word">skeuo<span className="brand-tld">.fm</span></span>
    </span>
  );
}
