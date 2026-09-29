export async function apiRequest<T = any>(url: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
    if ((response.status === 502 || response.status === 504) && (!options.method || options.method.toUpperCase() === 'GET')) {
      await new Promise((r) => setTimeout(r, 400));
      response = await fetch(url, { ...options, headers });
    }
  } catch (err) {
    if (!options.method || options.method.toUpperCase() === 'GET') {
      await new Promise((r) => setTimeout(r, 400));
      response = await fetch(url, { ...options, headers });
    } else {
      throw err;
    }
  }

  if (!response.ok) {
    let errorMsg = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const text = await response.text();
      if (text && text.trim()) {
        try {
          const errJson = JSON.parse(text);
          if (errJson.detail) errorMsg = errJson.detail;
          else if (errJson.message) errorMsg = errJson.message;
          else if (errJson.error) errorMsg = errJson.error;
          else errorMsg = text.trim();
        } catch (_) {
          errorMsg = text.trim();
        }
      }
    } catch (_) {}
    throw new Error(errorMsg);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json();
  }
  return response.text() as unknown as T;
}
