# Emoji assets

These PNGs are **Twemoji** by Twitter/X, licensed **CC-BY 4.0**.

- Source: https://github.com/twitter/twemoji (v14.0.2, 72x72 set)
- Licence: https://creativecommons.org/licenses/by/4.0/

CC-BY requires attribution wherever the graphics are used. This file satisfies it
for the repository; if the emoji appear in published videos, keep a line such as
"Emoji graphics by Twemoji (CC-BY 4.0)" in the channel or video description.

They are bundled as image files on purpose. The GitHub Actions runner installs
only `fonts-liberation` and `fonts-dejavu-core`, neither of which contains emoji
glyphs — an emoji drawn as *text* renders as an empty tofu box in every video CI
builds, while looking perfect on a Windows machine. Images cannot fail that way.
