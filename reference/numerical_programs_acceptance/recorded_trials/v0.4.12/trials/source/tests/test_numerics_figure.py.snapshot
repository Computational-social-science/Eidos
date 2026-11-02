"""Publication exports must preserve data, physical size and editable vector text."""
import math
import xml.etree.ElementTree as ET

from tools.numerics_case import build_case


def test_nature_exports_have_physical_size_text_and_no_raster(tmp_path):
    from tools.numerics_figure import render_figures
    policy = render_figures(tmp_path, build_case())
    assert policy["width_mm"] == 183 and policy["height_mm"] <= 170
    assert 5 <= policy["font_pt"] <= 7
    for dtype in ("float32", "float64"):
        svg = ET.parse(tmp_path / f"figure-{dtype}.svg").getroot()
        assert math.isclose(float(svg.attrib["width"].removesuffix("pt")) / 72 * 25.4, 183)
        assert len(svg.findall(".//{http://www.w3.org/2000/svg}text")) > 20
        assert not svg.findall(".//{http://www.w3.org/2000/svg}image")
        assert "exact zero" in "".join(svg.itertext()).lower()
        pdf = (tmp_path / f"figure-{dtype}.pdf").read_bytes()
        assert pdf.startswith(b"%PDF") and b"/FontFile2" in pdf


def test_zero_gradients_are_not_replaced_with_an_invented_positive_floor():
    from tools.numerics_figure import create_figure
    import matplotlib.pyplot as plt
    figure = create_figure(build_case(), "float32")
    try:
        standard = next(line for line in figure.axes[0].lines if line.get_label() == "Standard")
        assert any(math.isnan(y) for y in standard.get_ydata())
        assert len(figure.axes) == 4
        assert all(5 <= text.get_fontsize() <= 7 for axis in figure.axes
                   for text in [axis.title, axis.xaxis.label, axis.yaxis.label])
    finally:
        plt.close(figure)
