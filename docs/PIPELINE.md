# Pipeline notes

## Why this exists

Image generators often fake transparency by drawing checkerboard patterns. This project avoids that failure mode by treating transparency as a post-processing and verification requirement.

The preferred source image is not “transparent.” It is an ordinary image with the subject isolated on a flat, boring, removable background.

## Pipeline

```text
source image
  → native-alpha sanitize, if source already has alpha
  → simple solid-background matte
  → multiple rembg model variants
  → optional InSPyReNet variants
  → RGBA sanitization
  → optional edge decontamination
  → alpha/stats/audit composites
  → HTML preview over multiple solid backgrounds
  → save chosen variant
```

## Important details

### RGBA check

A true result must have an alpha channel and cannot be fully opaque. The pipeline reports:

- image mode
- alpha min/max
- transparent pixel count
- semi-transparent pixel count
- hidden RGB under fully transparent pixels
- checkerboard suspicion score

### Hidden RGB cleanup

Pixels with alpha `0` can still carry hidden RGB data. The sanitizer clears hidden RGB under fully transparent pixels.

### Edge decontamination

When the source image was generated on a known flat background, semi-transparent edge pixels can retain that background colour. The decontamination step estimates or accepts that colour and attempts to solve:

```text
observed = alpha * foreground + (1 - alpha) * background
```

for the foreground colour.

### Checkerboard detection

The checkerboard detector is only a hint. A generated subject can naturally contain repeating patterns, and a subtle baked checkerboard may evade detection. The decisive test is the preview over many solid backgrounds.

## Recommended backgrounds for inspection

Use at least:

- black
- white
- magenta
- blue
- mid gray
- a saturated warm colour
- a saturated cool colour

The preview includes 16 swatches by default.

## Variants

Default variants are selected to give a useful spread:

- preserve/sanitize existing alpha
- non-AI solid-background matte
- rembg U2Net models
- rembg ISNet model
- rembg BiRefNet models

Optional InSPyReNet support is available with `./install.sh --inspyrenet`.
