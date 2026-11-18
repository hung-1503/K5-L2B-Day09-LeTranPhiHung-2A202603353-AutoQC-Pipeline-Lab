from pipeline.checks.aspect_ratio import run


def test_aspect_ratio_uses_pixel_dimensions_and_config(make_ds, cfg):
    ds = make_ds(images={"sample": 1}, size=(400, 200), labels={"sample": [
        "0 .5 .5 .25 .125",
        "0 .5 .5 .0625 .5",
        "0 .5 .5 .25 .0625",
    ]})
    cfg["aspect_ratio"] = {"max_ratio": 4}

    issues = run(ds, cfg)

    assert [(issue.image, issue.line, issue.code, issue.severity, issue.extra["ratio"])
            for issue in issues] == [("sample", 3, "BOX_EXTREME_ASPECT", "warn", 8.0)]


def test_skips_invalid_rows_and_keeps_original_line_numbers(make_ds, cfg):
    ds = make_ds(images={"sample": 1, "corrupt": b"bad image", "unlabeled": 2},
                 size=(320, 320), labels={
                     "sample": ["broken", "inf .5 .5 .5 .01", "0 .5 .5 0 .5",
                                "8 .5 .5 .5 .01", "", "1 .5 .5 .01 .5"],
                     "corrupt": ["0 .5 .5 .5 .01"],
                 })

    issues = run(ds, cfg)

    assert [(issue.image, issue.line, issue.extra["ratio"]) for issue in issues] == [
        ("sample", 6, 50.0),
    ]
