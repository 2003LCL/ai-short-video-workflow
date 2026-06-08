# Style Controls

The product should let users adjust the generated video after the first draft.

These controls should eventually appear in the web UI as simple selectors, not as raw JSON.

## Aspect Ratio

Supported values:

```json
{
  "aspect_ratio": "9:16"
}
```

Options:

- `9:16`: vertical short video
- `16:9`: landscape video
- `1:1`: square social video

The goal is not to force every customer into vertical video. The canvas should adapt to the user's source material and publishing need.

## Visual Style

Supported values:

```json
{
  "visual_style": "clean_clinic"
}
```

Options:

- `clean_clinic`: restrained, professional, suitable for clinic and service businesses
- `warm_local`: warmer local-business feel
- `bold_product`: stronger contrast, suitable for product/service promotion

## Future Website Panel

After a first video draft is generated, the user should be able to adjust:

- aspect ratio
- visual style
- title size
- subtitle style
- accent color
- brand display
- image crop behavior
- background music mood
- voice style

Then the system should regenerate the preview without asking the user to restart the entire workflow.
