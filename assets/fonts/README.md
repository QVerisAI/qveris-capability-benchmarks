# Chart font assets

`QVerisCharts-Regular.otf` and `QVerisCharts-Bold.otf` are glyph-subset builds of
Noto Sans CJK SC from the official `notofonts/noto-cjk` repository. The chart
renderer loads these files explicitly instead of depending on system fonts.
Linux CI is the canonical rasterization environment and enforces byte-for-byte
equality with the committed PNGs; other platforms still verify the complete
structured chart data, input digests, and committed PNG digest.

The font software is distributed under the SIL Open Font License 1.1 in
`OFL-1.1.txt`. When chart labels change, regenerate both subsets from the
corresponding upstream Regular and Bold OTF files using printable ASCII
(`U+0020-007E`) plus the characters present in
`scripts/render_cap_guide_charts.py`. The current upstream file SHA-256 values
are `2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b`
for Regular and
`b5f0d1a190a7f9b43c310a8850630af12553df32c4c050543f9059732d9b4c0a`
for Bold.
