import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ENTRY_MODELS, ENTRY_MODEL_LABELS } from '@/lib/journal';
import type { EntryModel, JournalFilterState, JournalMode } from '@/types/api';

const ALL = '__all__';

/** Filter the journal list by mode / entry model / instrument. Controlled by
 * the page; backtest vs live is a first-class filter (the axes never blur). */
export function JournalFilters({
  value,
  onChange,
}: {
  value: JournalFilterState;
  onChange: (next: JournalFilterState) => void;
}) {
  const active = !!(value.mode || value.entry_model || value.instrument);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select
        value={value.mode ?? ALL}
        onValueChange={(v) => onChange({ ...value, mode: v === ALL ? undefined : (v as JournalMode) })}
      >
        <SelectTrigger className="h-9 w-[130px]" aria-label="Filter by mode">
          <SelectValue placeholder="All modes" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All modes</SelectItem>
          <SelectItem value="backtest">Backtest</SelectItem>
          <SelectItem value="live">Live</SelectItem>
        </SelectContent>
      </Select>

      <Select
        value={value.entry_model ?? ALL}
        onValueChange={(v) => onChange({ ...value, entry_model: v === ALL ? undefined : (v as EntryModel) })}
      >
        <SelectTrigger className="h-9 w-[190px]" aria-label="Filter by entry model">
          <SelectValue placeholder="All models" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All models</SelectItem>
          {ENTRY_MODELS.map((m) => (
            <SelectItem key={m} value={m}>
              {ENTRY_MODEL_LABELS[m]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Input
        value={value.instrument ?? ''}
        onChange={(e) => onChange({ ...value, instrument: e.target.value || undefined })}
        placeholder="Instrument (e.g. NQ)"
        className="h-9 w-[160px]"
        aria-label="Filter by instrument"
      />

      {active && (
        <Button variant="ghost" size="sm" className="h-9" onClick={() => onChange({})}>
          <X className="mr-1 h-3.5 w-3.5" /> Clear
        </Button>
      )}
    </div>
  );
}
