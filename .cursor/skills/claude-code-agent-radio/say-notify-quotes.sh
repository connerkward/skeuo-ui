#!/bin/bash
# Movie/game/military quote pools for say-notify "quotes" mode (SAY_MODE=quotes),
# an alternative to the default radio-chatter. Sourced by say-notify.sh. Routed by
# notification type: warning (mutating-tool permission), action (benign permission),
# idle (waiting). Full inspiration bank: say-notify-phrases.md.
warning_q=(
  "Pull up." "Terrain. Pull up." "Altitude. Altitude." "Warning. Warning."
  "Flares. Flares." "Bingo." "Brace for impact." "Red alert." "Enemy AC-130 above."
  "Predator missile inbound." "Obstruction detected. Engaging." "Embrace democracy."
  "Hull breach detected." "Decompression imminent." "Collision alert." "Proximity alert."
  "DEFCON 1." "Traffic. Traffic." "Go around. Go around." "Super Six-Four is going down."
  "We got a Black Hawk down." "Covenant inbound." "The ring is firing."
)
action_q=(
  "Buckle up." "Going hot." "All hands on deck." "Battle stations." "Lock and load."
  "Engage." "Eyes up." "Strap in, chucklenuts." "Prepare for jump." "Stay frosty."
  "Stay sharp." "Light the fires, kick the tires." "We're in the pipe, five by five."
  "Let's rock!" "Come on you apes, do you want to live forever?" "Enemy UAV online."
  "Care package inbound." "Hostiles inbound." "Frag out!" "Contact!" "Oscar Mike."
  "EMP activated." "Go for launch." "All systems go." "Be advised." "Get some."
  "Democracy is non-negotiable." "All systems nominal." "Service guarantees citizenship."
  "I'm doing my part!" "We're in it for the species!" "Make it so." "Shields up."
  "Cleared for takeoff." "Cleared to land." "You are cleared hot." "Stay on target."
  "Finish the fight." "Sir, finishing this fight." "I need a weapon." "Pelican inbound."
  "Were it so easy."
)
idle_q=(
  "Yo Big Dog!" "Beep boop." "Moshi moshi." "Hey bestie." "Gather round." "So picture this."
  "So here's the thing." "Story time." "Real talk." "My brother in christ." "Greetings, meatbag."
  "Incoming transmission." "Comms are live." "Stand by for orders." "We have a situation."
  "Saddle up." "Houston, do you copy?" "Houston." "Mission control, standing by."
  "Would you like to know more?" "They mostly come at night. Mostly." "Game over, man!"
  "Cool it." "Can you dig it?" "Lay it on me." "Bet." "Mickey Mouse bullshit."
  "Opening pod bay doors." "Shall we play a game?" "How about a nice game of chess?"
  "The only winning move is not to play." "Greetings, Professor Falken." "Talk to me, Goose."
  "Say again your last." "How do you read?" "Radio check." "Say your intentions."
  "Wake me when you need me." "Don't make a promise you can't keep."
  "Good enough for army work."
)
