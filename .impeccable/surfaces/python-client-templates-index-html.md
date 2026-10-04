---
version: 1
slug: "python-client-templates-index-html"
primary_target: "python/client/templates/index.html"
related_targets: []
---

# Control panel (python/client/templates/index.html)

Mode: Operate. Owner on a phone, tinkering often, panel on the wall in view.
Task: change the look and behaviour, see it land on the panel in a second.
Constraint: no CDNs, fonts self-hosted; every existing field, route and
script behaviour kept. Two switchable skins on one structure (owner chose
"develop both").

## Direction contract

THESIS: The control panel is a piece of audio equipment, not a web dashboard.
Refuses the category default of rounded cards on a dark gradient with a neon
accent (the old purple vaporwave page).

OWN-WORLD: Two skins, one structure. RACK: stacked rack units in dark
anodised grey (#1d1f22 on #121314), a left "ear" with two screw heads and
the unit's name engraved vertically, engraved Barlow Semi Condensed small
caps, light-grey legends, green/amber/red signal LEDs as the only colour,
label-tape style names on the style picker. SKIN: an early-2000s media
player done crisp: graphite bevelled chrome, a title bar per window, a
green-on-black LCD readout strip in Silkscreen/Share Tech Mono, square
bevelled buttons that depress when chosen, slider tracks like EQ faders.

STORY: Open the page, see the panel and what it's doing, change one thing,
watch the readout confirm it.

FIRST VIEWPORT: The live panel snapshot framed like equipment (a display
window / a meter bridge), status as an instrument readout (LEDs and a
readout line), then Display controls.

SIGNATURE: Choosing a style or mode lights its indicator LED / depresses its
button, and the readout prints "SAVED" like a device acknowledging.

RISK: Costume. Keep it legible and touch-sized: 44px targets, 4.5:1 text,
no fake screws larger than the content, no textures that fight the text.
