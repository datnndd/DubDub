# Backend ASS & Video Burn-in Survey Report (R2)

**Explorer Role**: Backend ASS & Video Burn-in Explorer  
**Working Directory**: `C:\Users\ddat2\Downloads\Projects\pyvideotrans\.agents\teamwork_preview_explorer_survey_be_r3`  
**Date**: 2026-09-29  
**Target Milestone**: R2 Complete Video Generation with Embedded Subtitles (Burn-in)

---

## 1. Observation

### 1.1 Render Request Payload & Task Params Deserialization

#### Frontend: `frontend/src/store/editVideoSlice.ts`
- **Lines 8–26 (`buildRenderRequest`)**:
  ```typescript
  export function buildRenderRequest(state: any) {
    return {
      mediaId: state.backend.mediaId,
      projectId: state.activeProjectId,
      jobType: 'render',
      options: {
        ...state.backend.config,
        audioMix: state.editVideo.audioMix,
        originalAudioVolume: state.editVideo.audioMix.original / 100,
        backgroundAudioVolume: state.editVideo.audioMix.background / 100,
        subtitleStyle: state.subtitleStyles,
        segments: state.segments,
        speakerVoiceMap: state.speakerVoiceMap,
        segmentVoiceOverrides: state.segmentVoiceOverrides,
        backgroundAudioId: state.editVideo.backgroundAudio?.id,
        thumbnailId: state.editVideo.thumbnail?.id,
      },
    };
  }
  ```
- **Lines 45–58 (`subtitleStyles` Initial State)**:
  ```typescript
  subtitleStyles: {
    preset: 'clean',
    fontFamily: 'Arial',
    fontSize: 22,
    color: '#FFFFFF',
    outlineColor: '#000000',
    outlineWidth: 2,
    shadowColor: 'rgba(0,0,0,.75)',
    shadowSize: 2,
    aiLipSync: true,
    deReverb: true,
    faceRetouch: false,
    superRes4K: true,
  }
  ```
- **`frontend/src/types/editor.ts` Lines 7–20 (`SubtitleStyleSettings`)**:
  ```typescript
  export interface SubtitleStyleSettings {
    preset: string;
    fontFamily: string;
    fontSize: number;
    color: string;
    outlineColor: string;
    outlineWidth: number;
    shadowColor: string;
    shadowSize: number;
    aiLipSync?: boolean;
    deReverb?: boolean;
    faceRetouch?: boolean;
    superRes4K?: boolean;
  }
  ```
  *Direct Observation*: `fontWeight`, `fontStyle`, and `opacity` are completely missing from `SubtitleStyleSettings` and the default store state.

#### Backend Task Parameter Parser: `videotrans/api/task_params.py`
- **Line 225 & 233**:
  ```python
  "subtitle_type": 0 if is_asr_only else 1,
  ...
  "subtitle_style": options.get("subtitleStyle") if isinstance(options.get("subtitleStyle"), dict) else None,
  ```
- **`videotrans/task/taskcfg.py` Line 202**:
  ```python
  subtitle_style: Optional[dict] = None  # per-job hard subtitle appearance
  ```
  *Direct Observation*: The backend already accepts `options.get("subtitleStyle")` and sets `task.cfg.subtitle_style = options.get("subtitleStyle")`. However, it does not check the snake_case alias `options.get("subtitle_style")`.

---

### 1.2 ASS Subtitle Generation & Styling: `videotrans/util/_srt_ass.py`

- **Lines 45–60 (`style_override` Handling in `set_ass_font`)**:
  ```python
  if style_override:
      def ass_color(value: str, fallback: str) -> str:
          match = re.fullmatch(r'#([0-9a-fA-F]{6})', str(value or ''))
          if not match:
              return fallback
          rgb = match.group(1)
          return f"&H00{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}&"
      style.update({
          'Fontname': str(style_override.get('fontFamily') or style.get('Fontname', 'Arial')),
          'Fontsize': max(8, min(96, int(style_override.get('fontSize', style.get('Fontsize', 24))))),
          'PrimaryColour': ass_color(style_override.get('color'), '&H00FFFFFF&'),
          'OutlineColour': ass_color(style_override.get('outlineColor'), '&H00000000&'),
          'Outline': max(0, min(10, int(style_override.get('outlineWidth', 2)))),
          'Shadow': max(0, min(10, int(style_override.get('shadowSize', 2)))),
      })
  ```
- **Lines 61–85 (`default_style` Construction)**:
  ```python
  default_style = (
      f"Style: {style.get('Name', 'Default')},"
      f"{style.get('Fontname', 'Arial')},"
      f"{style.get('Fontsize', 16)},"
      f"{style.get('PrimaryColour', '&H00FFFFFF&')},"
      f"{style.get('SecondaryColour', '&H00FFFFFF&')},"
      f"{style.get('OutlineColour', '&H00000000&')},"
      f"{style.get('BackColour', '&H00000000&')},"
      f"{style.get('Bold', 0)},"
      f"{style.get('Italic', 0)},"
      f"{style.get('Underline', 0)},"
      f"{style.get('StrikeOut', 0)},"
      f"{style.get('ScaleX', 100)},"
      f"{style.get('ScaleY', 100)},"
      f"{style.get('Spacing', 0)},"
      f"{style.get('Angle', 0)},"
      f"{style.get('BorderStyle', 1)},"
      f"{style.get('Outline', 1)},"
      f"{style.get('Shadow', 0)},"
      f"{style.get('Alignment', 2)},"
      f"{style.get('MarginL', 10)},"
      f"{style.get('MarginR', 10)},"
      f"{style.get('MarginV', 10)},"
      f"{style.get('Encoding', 1)}\n"
  )
  ```
- **Lines 133–142 (`replacer` Function)**:
  ```python
  def replacer(match):
      format_line = None
      for line in match.group(0).splitlines():
          if line.strip().startswith("Format:"):
              format_line = line.strip() + "\n"
              break
      if not format_line:
          format_line = "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
      return f"[V4+ Styles]\n{format_line}{default_style}{bottom_style}"
  ```
- *Direct Observation*:
  1. `fontWeight` is **completely ignored**: `style.update` never sets `'Bold'`, leaving it at `style.get('Bold', 0)`.
  2. `fontStyle` is **completely ignored**: `style.update` never sets `'Italic'`, leaving it at `style.get('Italic', 0)`.
  3. `opacity` is **completely ignored**: `ass_color` has a hardcoded `&H00...&` alpha prefix (which means 100% opaque, 0 transparency).
  4. `fontFamily` does not sanitize CSS font fallback stacks (e.g. `'Arial, sans-serif'`) or `'System default'`, which can cause libass font lookup misses.

---

### 1.3 Subtitle Pipeline & Video Burn-in Execution

- **`videotrans/task/_stage_subtitle.py` Lines 67–72**:
  ```python
  if self.cfg.subtitle_type in [2, 4]:
      return os.path.basename(process_end_subtitle), subtitle_langcode

  process_end_subtitle_ass = set_ass_font(process_end_subtitle, self.cfg.subtitle_style)
  basename = os.path.basename(process_end_subtitle_ass)
  return basename, subtitle_langcode
  ```
  `self.cfg.subtitle_type` is set to `1` (hard subtitle burn-in) by `build_task_params` during `jobType == "render"`.
  `set_ass_font` is called with `process_end_subtitle` (which points to `<cache_folder>/end.srt`) and `self.cfg.subtitle_style`. It writes `<cache_folder>/end.ass` and returns the file path.
- **`videotrans/task/_stage_assemble.py` Lines 293–315**:
  ```python
  else:
      cmd1.append('-filter_complex')
      subtitle_filter = [f"[0:v]subtitles=filename='{subtitles_file}'[v_out]"]
      cmd2 = [
          "-map",
          "[v_out]",
          "-map",
          "1:a",
          "-c:v",
          f'libx{self.video_codec_num}',
          '-c:a',
          'copy',
      ]
      cmd3 = ["-movflags", "+faststart"]
      ...
      runffmpeg(cmd0 + cmd1 + subtitle_filter + cmd2 + enc_qua + cmd3,
                cmd_dir=self.cfg.cache_folder, force_cpu=True)
  ```
  - Subtitle filter: `[0:v]subtitles=filename='end.ass'[v_out]`.
  - Executed inside working directory `self.cfg.cache_folder` using FFmpeg with `libass`.
  - Also in hardware-accelerated encoding branch (`_get_hard_cfg`, line 401 & 428):
    `vf_string = f"[0:v]subtitles=filename='{subtitles_file}'[v_out]"`
- **Output Video Target Paths**:
  - `videotrans/task/_stage_assemble.py` Lines 328–331:
    ```python
    if Path(tmp_target_mp4).exists():
        self.cfg.targetdir_mp4 = self.cfg.targetdir_mp4[:-4] + _video_output_ext
        shutil.copy2(tmp_target_mp4, self.cfg.targetdir_mp4)
    ```
  - Output path resolved in `videotrans/api/task_params.py` Lines 102–108:
    - If `projectId` provided: `output/projects/{projectId}/exports/{noextname}.mp4`
    - If no `projectId`: `output/{safe_stem}/{noextname}.mp4`
  - Thumbnail embedding in `videotrans/task/orchestrator.py` Lines 332–347:
    `_embed_thumbnail(cfg)` embeds cover art without re-encoding video streams.

---

## 2. Logic Chain & Gap Analysis

```
Client buildRenderRequest
     │ options.subtitleStyle = {
     │   fontFamily, fontSize, fontWeight,
     │   fontStyle, opacity, color, outlineColor, outlineWidth, shadowSize
     │ }
     ▼
API build_task_params() [videotrans/api/task_params.py]
     │ params["subtitle_style"] = options.get("subtitleStyle")
     │ params["subtitle_type"] = 1 (hard burn-in)
     ▼
JobRunner full -> TransCreate [videotrans/task/trans_create.py]
     │ self.cfg.subtitle_style = params["subtitle_style"]
     │ task.assembling()
     ▼
_stage_assemble.py -> _process_subtitles() [_stage_subtitle.py]
     │ process_end_subtitle_ass = set_ass_font(end.srt, self.cfg.subtitle_style)
     ▼
_srt_ass.py (GAP OCCURS HERE)
     ├── fontFamily parsed, but no CSS stack / "System default" sanitization
     ├── fontSize parsed
     ├── color parsed -> hardcoded &H00BBGGRR& (IGNORES opacity!)
     ├── outlineColor, outlineWidth, shadowSize parsed
     ├── fontWeight IGNORED -> Bold remains 0 (Normal)
     └── fontStyle IGNORED -> Italic remains 0 (Normal)
     ▼
FFmpeg Assemble [_stage_assemble.py]
     │ -filter_complex "[0:v]subtitles=filename='end.ass'[v_out]"
     │ libass renders ASS onto video frames
     ▼
Result: Burned-in video lacks custom bold, italic, and opacity transparency!
```

### Table: Gap Analysis for Subtitle Style Parameters

| Style Parameter | Current Frontend State | Current Backend Deserialization | Current `_srt_ass.py` Mapping | R2 Requirement / Status |
|---|---|---|---|---|
| `fontFamily` | `'Arial'` | Passed through | `str(style_override.get('fontFamily'))` | Needs sanitization for `"System default"` -> `"Arial"` and comma-separated CSS stacks |
| `fontSize` | `22` | Passed through | `max(8, min(96, int(fontSize)))` | Compliant (slider 12–64px supported) |
| `fontWeight` | **Missing** | Passed through | **Not mapped (defaults to 0)** | **GAP**: Must map to ASS `Bold`: `-1` (bold), `0` (normal) |
| `fontStyle` | **Missing** | Passed through | **Not mapped (defaults to 0)** | **GAP**: Must map to ASS `Italic`: `-1` (italic), `0` (normal) |
| `opacity` | **Missing** | Passed through | **Not mapped (hardcoded 00)** | **GAP**: Must map to ASS `PrimaryColour` alpha byte `&HAABBGGRR&` |
| `color` | `'#FFFFFF'` | Passed through | `ass_color('#FFFFFF')` -> `&H00FFFFFF&` | Works, but must incorporate `opacity` alpha byte |
| `outlineColor` | `'#000000'` | Passed through | `ass_color('#000000')` -> `&H00000000&` | Compliant |
| `outlineWidth` | `2` | Passed through | `max(0, min(10, int(outlineWidth)))` | Compliant |
| `shadowSize` | `2` | Passed through | `max(0, min(10, int(shadowSize)))` | Compliant |

---

## 3. Precise Formulas & Mappings

### 3.1 ASS `Bold` Mapping Formula

In the ASS v4+ specification (`[V4+ Styles]` format), the `Bold` field is defined as:
- `-1`: Bold enabled (True)
- `0`: Normal font weight (False)

```python
def parse_ass_bold(weight_val: Any) -> int:
    """Map fontWeight or bold toggle to ASS Bold flag (-1 for bold, 0 for normal)."""
    if isinstance(weight_val, bool):
        return -1 if weight_val else 0
    if isinstance(weight_val, (int, float)):
        return -1 if (weight_val >= 600 or weight_val == -1) else 0
    if isinstance(weight_val, str):
        s = weight_val.strip().lower()
        if s in {"bold", "bolder", "true", "1", "-1"}:
            return -1
        if s.isdigit() and int(s) >= 600:
            return -1
    return 0
```

### 3.2 ASS `Italic` Mapping Formula

In the ASS v4+ specification, the `Italic` field is defined as:
- `-1`: Italic enabled (True)
- `0`: Normal font style (False)

```python
def parse_ass_italic(style_val: Any) -> int:
    """Map fontStyle or italic toggle to ASS Italic flag (-1 for italic, 0 for normal)."""
    if isinstance(style_val, bool):
        return -1 if style_val else 0
    if isinstance(style_val, (int, float)):
        return -1 if style_val != 0 else 0
    if isinstance(style_val, str):
        s = style_val.strip().lower()
        if s in {"italic", "oblique", "true", "1", "-1"}:
            return -1
    return 0
```

### 3.3 Opacity to ASS `PrimaryColour` Alpha Hex Mapping Formula

#### Specification
In ASS, colors are structured in hexadecimal as:
$$\&H\mathbf{AA}\mathbf{BB}\mathbf{GG}\mathbf{RR}\&$$
Where:
- $\mathbf{AA}$: Alpha transparency byte in range $[0, 255]$ ($00_{16} \dots \text{FF}_{16}$)
  - **`00`**: $0\%$ transparency = $100\%$ opacity (fully opaque, completely solid text)
  - **`FF`**: $100\%$ transparency = $0\%$ opacity (fully transparent, invisible text)
- $\mathbf{BB}$: Blue hex channel $[00 \dots \text{FF}]$
- $\mathbf{GG}$: Green hex channel $[00 \dots \text{FF}]$
- $\mathbf{RR}$: Red hex channel $[00 \dots \text{FF}]$

#### Formula
Given user opacity input $P$ (either as percentage $0 \le P \le 100$, string `"80%"`, or float $0.0 \le P \le 1.0$):
1. Normalize to $O_{\text{norm}} \in [0.0, 1.0]$:
   $$O_{\text{norm}} = \begin{cases} 
   \frac{\operatorname{clamp}(P, 0, 100)}{100} & \text{if } P > 1.0 \\
   \operatorname{clamp}(P, 0.0, 1.0) & \text{if } 0.0 \le P \le 1.0 
   \end{cases}$$
2. Calculate integer Alpha transparency byte:
   $$\text{Alpha Byte} = \operatorname{round}\left((1.0 - O_{\text{norm}}) \times 255\right)$$
3. Format as 2-character uppercase hex string:
   $$\text{AA}_{\text{hex}} = \text{Alpha Byte}_{16} \quad (\text{0-padded to 2 digits})$$
4. Convert RGB hex `#RRGGBB` to BGR hex:
   $$\text{ASS Color} = \&\text{H}\mathbf{AA}_{\text{hex}}\mathbf{BB}\mathbf{GG}\mathbf{RR}\&$$

#### Lookup / Proof Table

| Opacity Input | Normalized $O_{\text{norm}}$ | Alpha Calculation | Alpha Byte (Dec) | Alpha Hex ($\mathbf{AA}$) | Input Color `#RRGGBB` | Resulting ASS `PrimaryColour` |
|---|---|---|---|---|---|---|
| `100` (or `100%`) | `1.00` | $(1 - 1.0) \times 255 = 0.0$ | `0` | `00` | `#FFFFFF` | `&H00FFFFFF&` |
| `80` (or `80%`) | `0.80` | $(1 - 0.8) \times 255 = 51.0$ | `51` | `33` | `#FFFFFF` | `&H33FFFFFF&` |
| `80` (or `80%`) | `0.80` | $(1 - 0.8) \times 255 = 51.0$ | `51` | `33` | `#FF0000` (Red) | `&H330000FF&` |
| `50` (or `50%`) | `0.50` | $(1 - 0.5) \times 255 = 127.5$ | `128` | `80` | `#FFFF00` (Yellow)| `&H8000FFFF&` |
| `25` (or `25%`) | `0.25` | $(1 - 0.25) \times 255 = 191.25$| `191` | `BF` | `#00FF00` (Green) | `&HBF00FF00&` |
| `0` (or `0%`) | `0.00` | $(1 - 0.0) \times 255 = 255.0$ | `255` | `FF` | `#FFFFFF` | `&HFFFFFFFF&` |

### 3.4 Font Family Sanitization

```python
def sanitize_font_family(raw_font: Any) -> str:
    """Extract primary font and map web/system fallbacks to Arial."""
    if not raw_font:
        return "Arial"
    s = str(raw_font).strip().split(",")[0].strip().strip("'\"")
    if not s or s.lower() in {"system default", "system", "system-ui", "default", "sans-serif"}:
        return "Arial"
    return s
```

---

## 4. Proposed Backend Implementation Changes

### 4.1 In `videotrans/util/_srt_ass.py`

Replace lines 46–60 of `set_ass_font` with:

```python
    if style_override:
        # 1. Opacity parsing -> ASS Alpha byte (00 = fully opaque, FF = fully transparent)
        raw_opacity = style_override.get('opacity')
        alpha_byte = 0
        if raw_opacity is not None:
            try:
                op_str = str(raw_opacity).rstrip('%').strip()
                val = float(op_str)
                norm_op = (val / 100.0) if val > 1.0 else val
                norm_op = max(0.0, min(1.0, norm_op))
                alpha_byte = int(round((1.0 - norm_op) * 255.0))
            except (ValueError, TypeError):
                alpha_byte = 0

        def ass_color(value: str, fallback_hex: str = 'FFFFFF', alpha: int = 0) -> str:
            aa = f"{max(0, min(255, int(alpha))):02X}"
            hex_str = str(value or '').strip()
            match = re.fullmatch(r'#([0-9a-fA-F]{6})', hex_str)
            if match:
                rgb = match.group(1)
            else:
                rgb = fallback_hex.lstrip('#')
            return f"&H{aa}{rgb[4:6]}{rgb[2:4]}{rgb[0:2]}&"

        # 2. Font family sanitization
        raw_font = style_override.get('fontFamily') or style_override.get('font_family') or style.get('Fontname', 'Arial')
        font_name = str(raw_font).split(',')[0].strip().strip('\'"')
        if not font_name or font_name.lower() in {'system default', 'system', 'system-ui', 'default', 'sans-serif'}:
            font_name = 'Arial'

        # 3. Bold mapping (-1 for bold, 0 for normal)
        raw_weight = style_override.get('fontWeight') if 'fontWeight' in style_override else style_override.get('font_weight', style_override.get('bold'))
        is_bold = False
        if isinstance(raw_weight, bool):
            is_bold = raw_weight
        elif isinstance(raw_weight, (int, float)):
            is_bold = (raw_weight >= 600 or raw_weight == -1)
        elif isinstance(raw_weight, str):
            s = raw_weight.strip().lower()
            is_bold = (s in {'bold', 'bolder', 'true', '1', '-1'}) or (s.isdigit() and int(s) >= 600)
        bold_val = -1 if is_bold else 0

        # 4. Italic mapping (-1 for italic, 0 for normal)
        raw_style = style_override.get('fontStyle') if 'fontStyle' in style_override else style_override.get('font_style', style_override.get('italic'))
        is_italic = False
        if isinstance(raw_style, bool):
            is_italic = raw_style
        elif isinstance(raw_style, (int, float)):
            is_italic = raw_style != 0
        elif isinstance(raw_style, str):
            s = raw_style.strip().lower()
            is_italic = s in {'italic', 'oblique', 'true', '1', '-1'}
        italic_val = -1 if is_italic else 0

        style.update({
            'Fontname': font_name,
            'Fontsize': max(8, min(96, int(style_override.get('fontSize', style_override.get('font_size', style.get('Fontsize', 24)))))),
            'PrimaryColour': ass_color(style_override.get('color'), fallback_hex='FFFFFF', alpha=alpha_byte),
            'OutlineColour': ass_color(style_override.get('outlineColor', style_override.get('outline_color')), fallback_hex='000000', alpha=0),
            'Outline': max(0, min(10, int(style_override.get('outlineWidth', style_override.get('outline_width', 2))))),
            'Shadow': max(0, min(10, int(style_override.get('shadowSize', style_override.get('shadow_size', 2))))),
            'Bold': bold_val,
            'Italic': italic_val,
        })
```

### 4.2 In `videotrans/api/task_params.py`

Enhance line 233 to check both camelCase and snake_case:
```python
"subtitle_style": (
    options.get("subtitleStyle")
    if isinstance(options.get("subtitleStyle"), dict)
    else (options.get("subtitle_style") if isinstance(options.get("subtitle_style"), dict) else None)
),
```

### 4.3 In `tests/test_stage4_edit_video.py`

Add automated tests verifying that `_srt_ass.py` parses `fontWeight`, `fontStyle`, and `opacity`:
```python
def test_set_ass_font_style_overrides_bold_italic_opacity(tmp_path):
    """Verify that set_ass_font correctly parses bold (-1), italic (-1), and opacity hex alpha."""
    from videotrans.util._srt_ass import set_ass_font
    
    srt_file = tmp_path / "test.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:02,000\nHello Subtitle\n", encoding="utf-8")
    
    style_override = {
        "fontFamily": "Inter, sans-serif",
        "fontSize": 28,
        "fontWeight": "bold",
        "fontStyle": "italic",
        "opacity": 80,
        "color": "#FF0000",
        "outlineColor": "#000000",
        "outlineWidth": 3,
        "shadowSize": 1,
    }
    
    ass_path = set_ass_font(srt_file.as_posix(), style_override)
    ass_content = Path(ass_path).read_text(encoding="utf-8")
    
    # Assert Default style line contains:
    # Fontname = Inter
    # Fontsize = 28
    # PrimaryColour = &H330000FF& (80% opacity -> alpha 0x33, red BGR -> 0000FF)
    # Bold = -1
    # Italic = -1
    assert "Style: Default,Inter,28,&H330000FF&,&H00FFFFFF&,&H00000000&,&H00000000&,-1,-1" in ass_content
```

---

## 5. Caveats

1. **Local Font Availability for libass**:
   FFmpeg’s libass burns subtitles using fonts installed on the host operating system. If a font like `"Inter"` or `"Roboto"` is selected in the UI but not installed in the Windows/Linux font cache, fontconfig/libass will automatically fall back to the system sans-serif font (typically Arial on Windows). This is standard libass behavior.
2. **Dual-Subtitle Bottom Style**:
   In `_srt_ass.py`, `bottom_style` formats secondary bilingual text. If bilingual dual subtitles are enabled with custom styling, `bottom_style` can also inherit the primary font and bold/italic flags unless specifically set in `style`.
3. **Hardcoded vs Soft Subtitles**:
   For soft subtitles (`subtitle_type` 2 or 4), MP4 container uses `mov_text` and MKV uses `srt`, which do not carry ASS alpha/italic typography. R2 specifically targets hard subtitles (`subtitle_type = 1`), where ASS styles are fully rendered.

---

## 6. Conclusion

1. **Current Pipeline Health**: The end-to-end plumbing already exists: frontend `buildRenderRequest` sends `subtitleStyle`, backend `build_task_params` populates `subtitle_style`, and `_stage_assemble.py` executes FFmpeg with `-filter_complex "[0:v]subtitles=filename='end.ass'[v_out]"`.
2. **Missing Implementation**: The only gap preventing full typography customization in burned-in videos is located in `videotrans/util/_srt_ass.py:set_ass_font()`, where `fontWeight`, `fontStyle`, and `opacity` are completely absent from the style override update dictionary.
3. **Actionable Fix**: Applying the proposed changes to `_srt_ass.py` (and supporting types in `frontend/src/types/editor.ts` and `editVideoSlice.ts`) will cleanly satisfy R2 without requiring architectural modifications.

---

## 7. Verification Method

1. **Run Unit Tests**:
   Execute the Stage 4 unit tests to ensure all existing functionality remains healthy:
   ```bash
   uv run pytest tests/test_stage4_edit_video.py
   ```
2. **Run ASS Generation Test**:
   Execute the verification snippet in Python:
   ```bash
   uv run python -c "from videotrans.util._srt_ass import set_ass_font; import tempfile, Path; f = tempfile.NamedTemporaryFile('w', suffix='.srt', delete=False, encoding='utf-8'); f.write('1\n00:00:00,000 --> 00:00:02,000\nTest\n'); f.close(); res = set_ass_font(f.name, {'fontWeight': 'bold', 'fontStyle': 'italic', 'opacity': 80, 'color': '#FF0000'}); print(open(res, encoding='utf-8').read())"
   ```
   **Expected Output**: The `Style: Default` line must contain `-1` for Bold, `-1` for Italic, and `&H330000FF&` for PrimaryColour.
3. **Invalidation Conditions**:
   - `Bold` is `0` when `fontWeight: "bold"`.
   - `Italic` is `0` when `fontStyle: "italic"`.
   - `PrimaryColour` alpha channel is `00` instead of computed hex (e.g. `33` for 80% opacity).
