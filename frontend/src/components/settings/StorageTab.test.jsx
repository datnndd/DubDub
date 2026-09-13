import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import StorageTab from './StorageTab';

const INFO = {
  data_dir: '/home/u/.omnivoice',
  outputs_dir: '/home/u/.omnivoice/outputs',
  crash_log_path: '/home/u/.omnivoice/crash_log.txt',
};

/** URL-aware fetch mock: /system/info + history-retention + export/reveal. */
function mockFetch() {
  const fn = vi.fn(async (url) => {
    const body = /\/system\/info/.test(url)
      ? INFO
      : /history-retention/.test(url)
        ? { cap: 200, default: 200 }
        : { success: true };
    return {
      ok: true,
      status: 200,
      json: async () => body,
      text: async () => JSON.stringify(body),
    };
  });
  global.fetch = fn;
  return fn;
}

function renderTab() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <StorageTab />
    </QueryClientProvider>,
  );
}

describe('StorageTab', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('labels the data dir as app data and displays the paths', async () => {
    mockFetch();
    renderTab();
    await waitFor(() => expect(screen.getByText(`${INFO.data_dir}/`)).toBeInTheDocument());
    expect(screen.getByText('App data stored at')).toBeInTheDocument();
    expect(screen.getByText(INFO.outputs_dir)).toBeInTheDocument();
    expect(screen.getByText(INFO.crash_log_path)).toBeInTheDocument();
  });
});
