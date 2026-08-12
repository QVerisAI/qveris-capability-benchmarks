# Chart font assets

`QVerisCharts-Regular.otf` and `QVerisCharts-Bold.otf` are glyph-subset builds of
Noto Sans CJK SC from the official `notofonts/noto-cjk` repository. The chart
renderer loads these files explicitly instead of depending on system fonts.
Linux CI is the canonical rasterization environment and enforces byte-for-byte
equality with the committed PNGs; other platforms still verify the complete
structured chart data, input digests, and committed PNG digest.

The font software is distributed under the SIL Open Font License 1.1 in
`OFL-1.1.txt`. When chart labels change, regenerate both subsets from the
corresponding upstream Regular and Bold OTF files using the characters present
in `scripts/render_cap_guide_charts.py`.
