import React from 'react';
import { Cpu, Download, RefreshCw, Trash2 } from 'lucide-react';
import { toast } from 'react-hot-toast';
import { useTranslation } from 'react-i18next';
import { useDeleteModel, useInstallModel, useModels } from '../../api/hooks';
import { Badge, Button } from '../../ui';
import { SettingsSection } from './primitives';

/** The model boundary deliberately exposes one downloadable artifact only. */
export default function ModelStoreTab({ modelBadge }) {
  const { t } = useTranslation();
  const models = useModels();
  const install = useInstallModel();
  const remove = useDeleteModel();
  const model = models.data?.models?.find((entry) => entry.repo_id === 'k2-fsa/OmniVoice');
  const busy = install.isPending || remove.isPending;

  const run = async (action, success) => {
    try {
      await action();
      await models.refetch();
      toast.success(success);
    } catch (error) {
      toast.error(error?.message || String(error));
    }
  };

  return (
    <SettingsSection icon={Cpu} title="OmniVoice" actions={modelBadge}>
      {models.isLoading ? (
        <div className="settings-muted">{t('common.loading')}</div>
      ) : !model ? (
        <div className="settings-muted">—</div>
      ) : (
        <div className="flex flex-wrap items-center gap-[var(--space-3)] rounded-[var(--chrome-radius-pill)] bg-[var(--chrome-hover-bg)] p-[var(--space-4)]">
          <div className="min-w-0 flex-1">
            <div className="font-medium text-[var(--chrome-fg)]">k2-fsa/OmniVoice</div>
            <div className="text-[length:var(--text-xs)] text-[var(--chrome-fg-dim)]">
              {model.size_gb ? `${model.size_gb} GB` : '—'}
            </div>
          </div>
          <Badge tone={model.installed ? 'success' : 'warn'}>
            {model.installed ? t('models.installed') : t('models.not_installed')}
          </Badge>
          {model.installed ? (
            <Button
              size="sm"
              variant="danger"
              disabled={busy}
              loading={remove.isPending}
              leading={!remove.isPending && <Trash2 size={12} />}
              onClick={() => run(() => remove.mutateAsync(model.repo_id), t('models.deleted', { repoId: model.repo_id }))}
            >
              {t('models.delete_btn')}
            </Button>
          ) : (
            <Button
              size="sm"
              disabled={busy}
              loading={install.isPending}
              leading={!install.isPending && <Download size={12} />}
              onClick={() => run(() => install.mutateAsync(model.repo_id), t('models.install_started'))}
            >
              {t('models.install_btn')}
            </Button>
          )}
          <Button size="sm" variant="subtle" onClick={() => models.refetch()} disabled={busy} leading={<RefreshCw size={12} />}>
            {t('common.refresh')}
          </Button>
        </div>
      )}
    </SettingsSection>
  );
}
