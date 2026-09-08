"""Sequential cropped raw-video decoding, without intermediate image files."""
import json
import subprocess


def probe(video):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height:format=duration', '-of', 'json', video],
        capture_output=True, check=True, timeout=30,
    )
    data = json.loads(result.stdout)
    stream = data['streams'][0]
    return stream['width'], stream['height'], float(data['format']['duration'])


def sampled_frame_iter(video, crop, fps=2.0, start_index=0, *, window_start=0.0, window_end=None):
    import numpy as np

    width, height, duration = probe(video)
    x, y = round(width * crop['left']), round(height * crop['top'])
    w = max(1, round(width * crop['right']) - x)
    h = max(1, round(height * crop['bottom']) - y)
    # Trim after the fps filter retains the original sampling grid on resume.
    # Round source timestamps upward so an output slot uses the frame at that
    # timestamp, not a frame up to half a coarse interval in the future.
    filters = f'fps={fps}:round=up,trim=start_frame={start_index},crop={w}:{h}:{x}:{y}:exact=1'
    seek = ['-ss', str(window_start)] if window_start else []
    # Let the fps filter flush the last in-window sample; discard the extra
    # interval below rather than truncating its buffered output with -t.
    limit = ['-t', str(max(0, window_end - window_start) + 1 / fps)] if window_end is not None else []
    with subprocess.Popen(
        ['ffmpeg', '-nostdin', '-v', 'error', *seek, '-i', video, *limit, '-an', '-sn',
         '-vf', filters, '-f', 'rawvideo', '-pix_fmt', 'bgr24', 'pipe:1'],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as process:
        try:
            index = start_index
            size = w * h * 3
            while True:
                body = bytearray()
                while len(body) < size:
                    chunk = process.stdout.read(size - len(body))
                    if not chunk:
                        break
                    body.extend(chunk)
                if not body:
                    break
                if len(body) != size:
                    raise RuntimeError('Truncated OCR video frame')
                timestamp = window_start + index / fps
                if window_end is None or timestamp < window_end:
                    yield index, min(timestamp, duration), np.frombuffer(body, dtype=np.uint8).reshape(h, w, 3)
                index += 1
            if process.wait(timeout=30):
                raise RuntimeError('OCR video decoder failed')
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)
