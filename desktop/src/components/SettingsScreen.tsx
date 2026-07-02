import { HelpCircle, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Label, Segmented, Select, Switch } from "@/components/ui/controls";
import { useToast } from "@/components/ui/toast";
import { getBridge } from "@/lib/bridge";
import { isExternalProvider, PROVIDER_BASE_URLS } from "@/lib/providers";
import type { AppSettings, ChunkingMode, ComputeType, SummaryMode, SummaryProvider, WhisperDevice } from "@/lib/types";
import { cn } from "@/lib/utils";

type SectionId = "transcription" | "summarization" | "preprocessing" | "general";

// Tabs follow the pipeline order: preprocess → transcribe → summarize, then everything else
// (папка результатов, приватность, ключи) folded into one «Общие» tab.
const SECTIONS: { id: SectionId; label: string }[] = [
  { id: "preprocessing", label: "Предобработка" },
  { id: "transcription", label: "Транскрибация" },
  { id: "summarization", label: "Суммаризация" },
  { id: "general", label: "Общие" },
];

interface SettingsScreenProps {
  settings: AppSettings;
  onSaved: () => Promise<AppSettings>;
}

export function SettingsScreen({ settings, onSaved }: SettingsScreenProps) {
  const { toast } = useToast();
  const [section, setSection] = useState<SectionId>("transcription");
  const [draft, setDraft] = useState<AppSettings>(() => structuredClone(settings));
  const [saving, setSaving] = useState(false);

  const dirty = useMemo(() => JSON.stringify(draft) !== JSON.stringify(settings), [draft, settings]);

  const update = (mutate: (d: AppSettings) => void) =>
    setDraft((prev) => {
      const next = structuredClone(prev);
      mutate(next);
      return next;
    });

  const save = async () => {
    setSaving(true);
    try {
      const bridge = await getBridge();
      await bridge.saveSettings(draft);
      const fresh = await onSaved();
      setDraft(structuredClone(fresh));
      toast("Настройки сохранены", "ok");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Не удалось сохранить настройки", "error");
    } finally {
      setSaving(false);
    }
  };

  const reset = () => setDraft(structuredClone(settings));

  return (
    <main className="flex flex-1 flex-col overflow-hidden bg-app">
      <header className="flex h-[58px] items-center justify-between border-b border-border bg-panel px-[18px]">
        <h1 className="text-xl font-semibold text-ink">Настройки</h1>
        {dirty && <span className="text-base text-warn">Есть несохранённые изменения</span>}
      </header>

      <div className="flex min-h-0 flex-1">
        <nav className="w-48 shrink-0 border-r border-border bg-panel p-3.5">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              onClick={() => setSection(s.id)}
              className={cn(
                "mb-0.5 flex h-[34px] w-full items-center rounded-md px-2.5 text-left text-base transition-colors",
                section === s.id ? "bg-accent-soft font-semibold text-accent" : "text-ink hover:bg-app",
              )}
            >
              {s.label}
            </button>
          ))}
        </nav>

        <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
          <div className="max-w-[720px] px-7 pb-20 pt-6">
            {section === "transcription" && <TranscriptionSection draft={draft} update={update} />}
            {section === "summarization" && <SummarizationSection draft={draft} update={update} />}
            {section === "preprocessing" && <PreprocessingSection draft={draft} update={update} />}
            {section === "general" && (
              <GeneralSection draft={draft} update={update} settings={settings} refresh={onSaved} />
            )}
          </div>
        </div>
      </div>

      <footer className="flex h-[58px] items-center justify-between border-t border-border bg-panel px-[18px]">
        <span className="flex items-center gap-1.5 text-base text-warn">
          {dirty && <span className="h-2 w-2 rounded-full bg-warn" />}
          {dirty ? "Есть несохранённые изменения" : <span className="text-ink-muted">Все изменения сохранены</span>}
        </span>
        <div className="flex gap-2">
          <Button variant="secondary" size="lg" onClick={reset} disabled={!dirty || saving}>
            Отменить
          </Button>
          <Button variant="primary" size="lg" onClick={save} disabled={!dirty || saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin" />} Сохранить
          </Button>
        </div>
      </footer>
    </main>
  );
}

// ── shared layout ──────────────────────────────────────────────────────────

type UpdateFn = (mutate: (d: AppSettings) => void) => void;

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-[18px] text-lg font-semibold text-ink">{children}</h2>;
}

function FormGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-2 gap-x-4 gap-y-3.5">{children}</div>;
}

function Field({
  label,
  hint,
  tooltip,
  full,
  children,
}: {
  label: string;
  hint?: string;
  tooltip?: string;
  full?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", full && "col-span-2")}>
      <div className="flex items-center gap-1">
        <Label>{label}</Label>
        {tooltip && (
          <span title={tooltip} aria-label={tooltip} className="cursor-help text-ink-soft hover:text-ink-muted">
            <HelpCircle className="h-3.5 w-3.5" />
          </span>
        )}
      </div>
      {children}
      {hint && <span className="text-sm text-ink-soft">{hint}</span>}
    </div>
  );
}

function numberInput(value: number, onChange: (n: number) => void, props?: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <Input
      type="number"
      value={Number.isFinite(value) ? value : ""}
      onChange={(e) => onChange(Number(e.target.value))}
      {...props}
    />
  );
}

function nullableNumberInput(value: number | null, onChange: (n: number | null) => void, placeholder = "не задано") {
  return (
    <Input
      type="number"
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
    />
  );
}

// ── sections ─────────────────────────────────────────────────────────────────

function TranscriptionSection({ draft, update }: { draft: AppSettings; update: UpdateFn }) {
  const t = draft.transcription;
  return (
    <div>
      <SectionTitle>Настройки транскрибации</SectionTitle>
      <FormGrid>
        <Field label="Язык" tooltip="На каком языке говорят в записи. «Авто» — определить автоматически.">
          <Select
            value={t.language}
            options={[
              { value: "ru", label: "Русский" },
              { value: "en", label: "English" },
              { value: "auto", label: "Авто" },
            ]}
            onChange={(e) => update((d) => (d.transcription.language = e.target.value))}
          />
        </Field>
        <Field label="Модель" tooltip="Размер модели Whisper: крупнее — точнее, но медленнее (напр. large-v3).">
          <Input value={t.model.name} onChange={(e) => update((d) => (d.transcription.model.name = e.target.value))} />
        </Field>
        <Field label="Устройство" tooltip="Где выполнять распознавание: CUDA — видеокарта (быстро), CPU — процессор (медленно).">
          <Select
            value={t.model.device}
            options={[
              { value: "cuda", label: "CUDA (GPU)" },
              { value: "cpu", label: "CPU" },
              { value: "auto", label: "Авто" },
            ]}
            onChange={(e) => update((d) => (d.transcription.model.device = e.target.value as WhisperDevice))}
          />
        </Field>
        <Field label="Точность (compute type)" tooltip="Формат вычислений. float16 — быстро на GPU, int8 — экономит память.">
          <Select
            value={t.model.compute_type}
            options={["default", "float16", "int8", "int8_float16", "float32"].map((v) => ({ value: v, label: v }))}
            onChange={(e) => update((d) => (d.transcription.model.compute_type = e.target.value as ComputeType))}
          />
        </Field>
        <Field label="Beam size" tooltip="Сколько вариантов распознавания перебирать. Больше — точнее, но медленнее.">
          {numberInput(t.model.beam_size, (n) => update((d) => (d.transcription.model.beam_size = n)), { min: 1 })}
        </Field>
        <Field label="VAD-фильтр" tooltip="Пропускать участки тишины, чтобы ускорить распознавание." hint="Пропускать тишину">
          <Switch checked={t.model.vad_filter} onChange={(v) => update((d) => (d.transcription.model.vad_filter = v))} />
        </Field>
        <Field label="Учитывать контекст" tooltip="Опираться на предыдущие фразы для связности (иногда повторяет ошибки).">
          <Switch
            checked={t.model.condition_on_previous_text}
            onChange={(v) => update((d) => (d.transcription.model.condition_on_previous_text = v))}
          />
        </Field>
      </FormGrid>
    </div>
  );
}

function SummarizationSection({ draft, update }: { draft: AppSettings; update: UpdateFn }) {
  const s = draft.summarization;
  return (
    <div>
      <SectionTitle>Настройки суммаризации</SectionTitle>
      <FormGrid>
        <Field label="Провайдер" tooltip="Сервис, делающий саммари. openai/xai — облачные; ollama/lm-studio/vllm — локальные.">
          <Select
            value={s.model.provider}
            options={["openai", "xai", "ollama", "lm-studio", "vllm"].map((v) => ({ value: v, label: v }))}
            onChange={(e) => update((d) => (d.summarization.model.provider = e.target.value as SummaryProvider))}
          />
        </Field>
        <Field label="Модель" tooltip="Название модели у провайдера (напр. gpt-4o, llama3).">
          <Input value={s.model.name} onChange={(e) => update((d) => (d.summarization.model.name = e.target.value))} />
        </Field>
        <Field
          label="Base URL"
          full
          tooltip="Адрес сервера провайдера. Обычно оставьте пустым — подставится значение по умолчанию."
          hint={`По умолчанию для «${s.model.provider}»: ${PROVIDER_BASE_URLS[s.model.provider] ?? "—"}`}
        >
          <Input
            value={s.model.base_url ?? ""}
            placeholder={PROVIDER_BASE_URLS[s.model.provider] ?? "по умолчанию для провайдера"}
            onChange={(e) => update((d) => (d.summarization.model.base_url = e.target.value === "" ? null : e.target.value))}
          />
        </Field>
        <Field label="Язык саммари" tooltip="На каком языке писать саммари.">
          <Select
            value={s.language ?? "ru"}
            options={[{ value: "ru", label: "Русский" }]}
            onChange={(e) => update((d) => (d.summarization.language = e.target.value))}
          />
        </Field>
        <Field label="Режим" tooltip="Объём саммари: краткий, средний или подробный протокол.">
          <Segmented<SummaryMode>
            value={s.mode}
            onChange={(mode) => update((d) => (d.summarization.mode = mode))}
            options={[
              { value: "brief", label: "brief" },
              { value: "medium", label: "medium" },
              { value: "detailed", label: "detailed" },
            ]}
          />
        </Field>
        <Field label="Chunking" tooltip="Длинные встречи: chunk — обрабатывать по частям, truncate — обрезать до лимита.">
          <Segmented<ChunkingMode>
            value={s.chunking_mode}
            onChange={(mode) => update((d) => (d.summarization.chunking_mode = mode))}
            options={[
              { value: "chunk", label: "chunk" },
              { value: "truncate", label: "truncate" },
            ]}
          />
        </Field>
        <Field label="Макс. символов" tooltip="Максимум символов транскрипта, отправляемых модели за один запрос.">
          {numberInput(s.max_transcript_chars, (n) => update((d) => (d.summarization.max_transcript_chars = n)), { min: 1 })}
        </Field>
        <Field label="Timeout (сек)" tooltip="Сколько секунд ждать ответ модели, прежде чем прервать.">
          {numberInput(s.timeout_seconds, (n) => update((d) => (d.summarization.timeout_seconds = n)), { min: 1 })}
        </Field>
        <Field label="Retries" tooltip="Сколько раз повторить запрос при ошибке.">
          {numberInput(s.retries, (n) => update((d) => (d.summarization.retries = n)), { min: 0 })}
        </Field>
        <Field label="num_ctx" tooltip="Размер контекстного окна модели в Ollama (в токенах)." hint="Только Ollama">
          {nullableNumberInput(s.model.num_ctx, (v) => update((d) => (d.summarization.model.num_ctx = v)))}
        </Field>
      </FormGrid>
    </div>
  );
}

function PreprocessingSection({ draft, update }: { draft: AppSettings; update: UpdateFn }) {
  const p = draft.preprocessing;
  return (
    <div>
      <SectionTitle>Предобработка аудио</SectionTitle>
      <FormGrid>
        <Field label="Включить" tooltip="Готовить аудио перед распознаванием (конвертация, нормализация). Нужен ffmpeg." hint="Требуется ffmpeg">
          <Switch checked={p.enabled} onChange={(v) => update((d) => (d.preprocessing.enabled = v))} />
        </Field>
        <Field label="Нормализация громкости" tooltip="Выровнять громкость, чтобы тихие голоса были слышны." hint="EBU R128 loudnorm">
          <Switch
            checked={p.loudness_normalization}
            onChange={(v) => update((d) => (d.preprocessing.loudness_normalization = v))}
          />
        </Field>
        <Field label="Частота (Hz)" tooltip="Частота дискретизации. Для речи достаточно 16000 Гц.">
          {numberInput(p.sample_rate, (n) => update((d) => (d.preprocessing.sample_rate = n)), { min: 1 })}
        </Field>
        <Field label="Каналы" tooltip="Моно (1) обычно достаточно для речи и меньше по размеру.">
          <Select
            value={String(p.channels)}
            options={[
              { value: "1", label: "Моно (1)" },
              { value: "2", label: "Стерео (2)" },
            ]}
            onChange={(e) => update((d) => (d.preprocessing.channels = Number(e.target.value)))}
          />
        </Field>
        <Field label="Target LUFS" tooltip="Целевая громкость по стандарту EBU R128 (обычно −16…−23).">{numberInput(p.target_lufs, (n) => update((d) => (d.preprocessing.target_lufs = n)))}</Field>
        <Field label="True peak (dBTP)" tooltip="Максимальный пик громкости, чтобы избежать перегруза.">{numberInput(p.true_peak_db, (n) => update((d) => (d.preprocessing.true_peak_db = n)))}</Field>
        <Field label="Loudness range" tooltip="Допустимый разброс громкости.">{numberInput(p.loudness_range, (n) => update((d) => (d.preprocessing.loudness_range = n)))}</Field>
        <Field label="High-pass (Hz)" tooltip="Срезать низкие частоты (гул). Пусто — выключено." hint="Пусто — выкл">
          {nullableNumberInput(p.highpass_hz, (v) => update((d) => (d.preprocessing.highpass_hz = v)))}
        </Field>
        <Field label="Хранить temp-файл" tooltip="Не удалять подготовленный аудио-файл после обработки.">
          <Switch checked={p.keep_temp} onChange={(v) => update((d) => (d.preprocessing.keep_temp = v))} />
        </Field>
      </FormGrid>
    </div>
  );
}

function GeneralSection({
  draft,
  update,
  settings,
  refresh,
}: {
  draft: AppSettings;
  update: UpdateFn;
  settings: AppSettings;
  refresh: () => Promise<AppSettings>;
}) {
  return (
    <div className="flex flex-col gap-9">
      <div>
        <SectionTitle>Папка для результатов</SectionTitle>
        <FormGrid>
          <Field
            label="Папка"
            full
            tooltip="Куда сохранять транскрипт и саммари. Файлы называются по имени аудиофайла, поэтому разные встречи не перезаписывают друг друга."
            hint="Пусто — сохранять рядом с исходным аудиофайлом."
          >
            <Input
              value={draft.output_dir ?? ""}
              placeholder="рядом с аудиофайлом"
              onChange={(e) => update((d) => (d.output_dir = e.target.value === "" ? null : e.target.value))}
            />
          </Field>
        </FormGrid>
        <p className="mt-3 text-sm text-ink-muted">История и конфигурация хранятся в каталоге данных приложения.</p>
      </div>
      <PrivacySection draft={draft} update={update} />
      <KeysSection draft={draft} settings={settings} refresh={refresh} />
    </div>
  );
}

function PrivacySection({ draft, update }: { draft: AppSettings; update: UpdateFn }) {
  return (
    <div>
      <SectionTitle>Приватность</SectionTitle>
      <FormGrid>
        <Field label="Согласие на отправку" tooltip="Разрешить отправку текста транскрипта внешнему провайдеру без предупреждения.">
          <Switch checked={draft.privacy_ack} onChange={(v) => update((d) => (d.privacy_ack = v))} />
        </Field>
      </FormGrid>
      <div className="mt-3.5 flex flex-col gap-2 rounded-card border border-warn-line bg-warn-soft p-3">
        <strong className="text-base font-semibold text-ink">Внешний провайдер может получить текст транскрипта.</strong>
        <span className="text-sm text-warn">
          При использовании внешнего провайдера (например, OpenAI) текст транскрипта отправляется на внешний сервер.
        </span>
        <label className="flex cursor-pointer items-center gap-2 text-base text-ink">
          <input
            type="checkbox"
            className="h-3.5 w-3.5 accent-accent"
            checked={draft.privacy_ack}
            onChange={(e) => update((d) => (d.privacy_ack = e.target.checked))}
          />
          Я понимаю
        </label>
      </div>
    </div>
  );
}

function KeysSection({
  draft,
  settings,
  refresh,
}: {
  draft: AppSettings;
  settings: AppSettings;
  refresh: () => Promise<AppSettings>;
}) {
  const { toast } = useToast();
  const provider = draft.summarization.model.provider;
  // CODE-007: reflect the key state of the *drafted* provider, not only the saved one.
  const configured = settings.api_keys_configured?.[provider] ?? false;
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const external = isExternalProvider(draft.summarization.model.base_url, provider);

  const withBusy = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Ошибка хранилища ключей", "error");
    } finally {
      setBusy(false);
    }
  };

  const saveKey = () =>
    withBusy(async () => {
      if (!value.trim()) {
        toast("Введите ключ", "error");
        return;
      }
      const bridge = await getBridge();
      await bridge.setApiKey(provider, value.trim());
      setValue("");
      await refresh();
      toast("Ключ сохранён", "ok");
    });

  const deleteKey = () =>
    withBusy(async () => {
      const bridge = await getBridge();
      await bridge.deleteApiKey(provider);
      await refresh();
      toast("Ключ удалён", "ok");
    });

  const test = () =>
    withBusy(async () => {
      const bridge = await getBridge();
      const res = await bridge.testConnection(provider);
      toast(res.message, res.ok ? "ok" : "error");
    });

  return (
    <div>
      <SectionTitle>Ключи API</SectionTitle>
      <FormGrid>
        <Field label="Провайдер">
          <Input value={provider} disabled />
        </Field>
        <Field label="Новый ключ">
          <Input type="password" value={value} placeholder="вставьте ключ API" onChange={(e) => setValue(e.target.value)} />
        </Field>
      </FormGrid>

      <div className="mt-[18px] grid grid-cols-[1fr_auto] items-start gap-3 rounded-card border border-border bg-panel-soft p-3">
        <div>
          <h3 className="text-base font-semibold text-ink">API key</h3>
          <p className="mt-1 text-sm text-ink-muted">
            Ключ хранится в системном хранилище (Windows Credential Manager). В config.yaml он не записывается.
          </p>
        </div>
        <span
          className={cn(
            "inline-flex h-[30px] items-center rounded-md border px-2.5 text-base font-bold",
            configured ? "border-ok-line bg-ok-soft text-ok" : "border-border bg-app text-ink-muted",
          )}
        >
          {configured ? "Ключ сохранён" : "Ключ не сохранён"}
        </span>
        <div className="col-span-2 flex flex-wrap gap-2">
          <Button variant="primary" size="sm" onClick={saveKey} disabled={busy}>
            Сохранить ключ
          </Button>
          <Button variant="secondary" size="sm" onClick={test} disabled={busy}>
            Проверить подключение
          </Button>
          <Button variant="danger" size="sm" onClick={deleteKey} disabled={busy || !configured}>
            Удалить
          </Button>
        </div>
      </div>

      {!external && (
        <p className="mt-3 text-sm text-ink-muted">Локальный провайдер — ключ обычно не нужен.</p>
      )}
    </div>
  );
}
