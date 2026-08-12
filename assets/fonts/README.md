# Chart font assets

`QVerisCharts-Regular.otf` and `QVerisCharts-Bold.otf` are glyph-subset builds of
Noto Sans CJK SC from the official `notofonts/noto-cjk` repository. The chart
renderer loads these files explicitly so committed PNG evidence is reproducible
across macOS and Linux instead of depending on system fonts.

The font software is distributed under the SIL Open Font License 1.1 in
`OFL-1.1.txt`. When chart labels change, regenerate both subsets from the
corresponding upstream Regular and Bold OTF files using the characters present
in `scripts/render_cap_guide_charts.py`.
