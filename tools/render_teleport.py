"""Transporter-specific rendering checks and shareable previews."""
import json
import numpy as np
from PIL import Image, ImageDraw


def validate_and_preview(render, uniform, data, output, replace_source, save_frames=False):
    frames = [render(float(p)) for p in np.linspace(0, 1, 41)]
    assert np.array_equal(frames[0], data), 'First frame must preserve source'
    assert not frames[-1].any(), 'Final frame must be fully transparent'
    for frame in frames:
        assert not frame[data[:, :, 3] == 0].any(), 'Energy leaked outside source alpha'
        assert np.all(frame[:, :, :3] <= frame[:, :, 3:4]), 'Not premultiplied alpha'
    areas = [np.count_nonzero(f[:, :, 3] >= 254) for f in frames]
    assert all(b <= a for a, b in zip(areas, areas[1:])), 'Opaque area increased'

    # A different source RGB must make NO difference once only energy remains.
    # This distinguishes disappearing content from simply dimming a screenshot.
    alternate = data.copy()
    alternate[:, :, :3] = 255 - data[:, :, :3]
    replace_source(alternate)
    assert not np.array_equal(render(0.15), frames[6]), 'Early content vanished too soon'
    for index in (16, 20, 26, 32, 36):
        assert np.array_equal(render(index / 40), frames[index]), 'Window content survived in the wake'
    alternate_mid = render(0.225)
    replace_source(data)
    original_mid = render(0.225)
    difference = np.max(np.abs(alternate_mid[:, :, :3].astype(np.int16)
                               - original_mid[:, :, :3].astype(np.int16)), axis=2)
    retained = difference > 10
    source_mask = data[:, :, 3] > 0
    retained_bands = []
    for rows in np.array_split(np.arange(data.shape[0]), 3):
        fraction = float(np.mean(retained[rows][source_mask[rows]]))
        assert 0.03 < fraction < 0.95, 'Dissolve must break up throughout the window, without a directional wipe'
        retained_bands.append(fraction)
    for frame in frames[16:]:
        assert np.all(frame[:, :, 0] <= frame[:, :, 1]), 'Warm/red light appeared in the energy wake'
        assert np.all(frame[:, :, 1] <= frame[:, :, 2]), 'Energy wake must remain bluish white'
    assert np.count_nonzero(frames[26][:, :, 3] > 4) > 100, 'Lingering energy is missing'
    signatures = set()
    for value in np.linspace(0.031, 0.971, 18):
        uniform('seed', float(value))
        frame = render(0.6)
        assert not frame[data[:, :, 3] == 0].any()
        assert np.all(frame[:, :, :3] <= frame[:, :, 3:4])
        signatures.add(frame.tobytes())
    assert len(signatures) == 18, 'Close seeds did not vary the wake'
    uniform('seed', 0.37)

    height, width = data.shape[:2]
    background = Image.new('RGB', (width, height), (20, 25, 36))
    previews = []
    for frame in frames:
        alpha = frame[:, :, 3:4].astype(np.float32)
        straight = frame.copy()
        straight[:, :, :3] = np.clip(frame[:, :, :3].astype(np.float32) * 255
                                     / np.maximum(alpha, 1), 0, 255).astype(np.uint8)
        composed = background.convert('RGBA')
        composed.alpha_composite(Image.fromarray(straight))
        previews.append(composed.convert('RGB'))
    output.mkdir(parents=True, exist_ok=True)
    previews[0].save(output / 'teleport-preview.gif', save_all=True,
                     append_images=previews[1:] + [previews[-1]] * 18, duration=40, loop=0)
    sheet = Image.new('RGB', (width * 3 // 2, (height // 2 + 28) * 2), (13, 17, 25))
    draw = ImageDraw.Draw(sheet)
    for cell, index in enumerate((0, 6, 12, 16, 26, 38)):
        x, y = cell % 3 * (width // 2), cell // 3 * (height // 2 + 28)
        sheet.paste(previews[index].resize((width // 2, height // 2)), (x, y + 28))
        draw.text((x + 12, y + 6), f'{index / 40:.0%}' + (' / energy only' if index >= 16 else ''), fill='white')
    sheet.save(output / 'teleport-contact-sheet.png')
    if save_frames:
        np.savez_compressed(output / 'frames.npz', frames=np.stack(frames))
    (output / 'validation.json').write_text(json.dumps({
        'effect': 'teleport', 'frames': len(frames), 'distinct_wakes': len(signatures),
        'content_gone_by': 0.4, 'wake_pixels_at_65_percent': int(np.count_nonzero(frames[26][:, :, 3] > 4)),
        'premultiplied_alpha': True, 'source_alpha_bounds': True,
        'spatial_breakup_retained_bands': retained_bands, 'bluish_white_wake': True,
    }, indent=2) + '\n')
    print('PASS: exact endpoints, alpha bounds, monotonic opaque area; content absent by 40%,')
    print('      visible energy at 65%, and 18 distinct seeded wakes.')
    print('Preview:', output / 'teleport-preview.gif')
