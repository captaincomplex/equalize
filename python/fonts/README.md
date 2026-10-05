# Fonts for the song name on the panel

Pixel fonts, drawn with every LED fully on or off. The control panel's
*Text size* chooses one.

| Size | Font | Rows | Licence | Source |
|---|---|---|---|---|
| Small | Tom Thumb (`tom-thumb.*`) | 6 | MIT, Robey Pointer 2010 (`LICENSE-tom-thumb.txt`) | robey.lag.net/2010/01/23/tiny-monospace-font.html, via hzeller/rpi-rgb-led-matrix `fonts/` at commit 51d3231 |
| Medium (default) | X11 misc-fixed 5x7 (`5x7.*`) | 7 | Public domain ("Public domain font. Share and enjoy.", in the file) | Markus Kuhn's ucs-fonts, via hzeller/rpi-rgb-led-matrix `fonts/` at commit 51d3231 |
| Large | ChicagoFLF (`ChicagoFLF.ttf`) | 14 | Public domain (`README-ChicagoFLF.txt`) | ChicagoFLF 2.0, Robin Casady, via fontlibrary.org |

The `.bdf` files are the originals; the `.pil` + `.pbm` pairs are the same
fonts converted for Pillow (`PIL.BdfFontFile`), which is what Equalize loads.
Both cover Latin-1 (é, ü, ß, Å ...); other letters fall back to the nearest
plain one (see `song_info._printable`).
