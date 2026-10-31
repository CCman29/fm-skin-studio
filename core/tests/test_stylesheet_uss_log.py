from fmskin import logwatch, stylesheet, uss


def synthetic_sheet() -> dict:
    """A tiny StyleSheet typetree in the shape UnityPy returns (values made up)."""
    return {
        "m_Name": "Demo",
        "m_Rules": [
            {"m_ComplexSelectors": [{"m_Selectors": [{"m_Parts": [{"m_Value": "root", "m_Type": 4}], "m_PreviousRelationship": 0}]}],
             "m_Properties": [
                 {"m_Id": -1, "m_CustomName": "--brand", "m_Line": 2, "m_Values": [{"m_ValueType": 4, "valueIndex": 0}]},
                 {"m_Id": -1, "m_CustomName": "--panel", "m_Line": 3,
                  "m_Values": [{"m_ValueType": 10, "valueIndex": 1}, {"m_ValueType": 2, "valueIndex": 0},
                               {"m_ValueType": 8, "valueIndex": 0}]}], "line": 1},
            {"m_ComplexSelectors": [{"m_Selectors": [
                {"m_Parts": [{"m_Value": "card", "m_Type": 3}], "m_PreviousRelationship": 0},
                {"m_Parts": [{"m_Value": "title", "m_Type": 3}, {"m_Value": "hover", "m_Type": 4}], "m_PreviousRelationship": 1}]}],
             "m_Properties": [
                 {"m_Id": 458752, "m_CustomName": "", "m_Line": 6,
                  "m_Values": [{"m_ValueType": 10, "valueIndex": 1}, {"m_ValueType": 2, "valueIndex": 0},
                               {"m_ValueType": 8, "valueIndex": 1}]},
                 {"m_Id": 131105, "m_CustomName": "", "m_Line": 7, "m_Values": [{"m_ValueType": 3, "valueIndex": 0}]}], "line": 5},
        ],
        "floats": [1.0], "dimensions": [{"unit": 2, "value": 50.0}],
        "colors": [{"r": 1.0, "g": 0.5, "b": 0.0, "a": 0.25}], "strings": ["--brand", "--panel"], "assets": [],
    }


def test_decode_to_uss():
    text = stylesheet.decode(synthetic_sheet()).to_uss()
    assert "--brand: rgba(255, 128, 0, 0.25);" in text
    assert "--panel: var(--brand);" in text
    assert ".card > .title:hover {" in text
    assert "background-color: var(--panel);" in text and "width: 50%;" in text


def test_uss_parse_lines_and_errors():
    doc = uss.parse("/* c\n */\n:root {\n  --a: rgb(1,2,3);\n}\n.x { color red; }\n.y { width: 1px;")
    assert doc.rules[0].decls[0].line == 4
    assert any("without ':'" in m for _, m in doc.errors)
    assert any("Missing closing" in m for _, m in doc.errors)


def test_check_value():
    assert uss.check_value("rgba(1, 2, 3, 0.5)") is None
    assert uss.check_value("rgba(1, 2, 3)") == "rgba() needs 4 numbers"
    assert uss.check_value("var(--a") == "unbalanced parentheses"


def test_log_events():
    log = ("noise\n[Skins] Ignoring skin 'zz-probe-broken': skin.json is malformed or lists no sheets.\n"
           "[USS] skin sheet 'mine/tokens.uss' decoded to 0 applied rules -- x\n")
    events = logwatch.parse_lines(log)
    assert [e.kind for e in events] == ["ignored", "uss"]
    assert events[0].skin == "zz-probe-broken" and events[1].skin == "mine"
