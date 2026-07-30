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
import {
  HYPOTHETICAL_OUTCOME_LABELS,
  MISS_TYPES,
  MISS_TYPE_LABELS,
} from '@/lib/missed-trades';
import type {
  EntryModel,
  HypotheticalOutcome,
  MissedFilterState,
  MissType,
} from '@/types/api';

const ALL = '__all__';

/** Filter the missed log by miss type / model / hypothetical outcome / instrument. */
export function MissedFilters({
  value,
  onChange,
}: {
  value: MissedFilterState;
  onChange: (next: MissedFilterState) => void;
}) {
  const active = !!(
    value.miss_type || value.entry_model || value.hypothetical_outcome || value.instrument
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Select
        value={value.miss_type ?? ALL}
        onValueChange={(v) =>
          onChange({ ...value, miss_type: v === ALL ? undefined : (v as MissType) })
        }
      >
        <SelectTrigger className="h-9 w-[210px]" aria-label="Filter by miss type">
          <SelectValue placeholder="All miss types" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>All miss types</SelectItem>
          {MISS_TYPES.map((m) => (
            <SelectItem key={m} value={m}>
              {MISS_TYPE_LABELS[m]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={value.entry_model ?? ALL}
        onValueChange={(v) =>
          onChange({ ...value, entry_model: v === ALL ? undefined : (v as EntryModel) })
        }
      >
        <SelectTrigger className="h-9 w-[190px]" aria-label="Filter missed by entry model">
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

      <Select
        value={value.hypothetical_outcome ?? ALL}
        onValueChange={(v) =>
          onChange({
            ...value,
            hypothetical_outcome: v === ALL ? undefined : (v as HypotheticalOutcome),
          })
        }
      >
        <SelectTrigger className="h-9 w-[200px]" aria-label="Filter by hypothetical outcome">
          <SelectValue placeholder="Any outcome" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL}>Any outcome</SelectItem>
          {Object.entries(HYPOTHETICAL_OUTCOME_LABELS).map(([v, l]) => (
            <SelectItem key={v} value={v}>
              {l}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Input
        value={value.instrument ?? ''}
        onChange={(e) => onChange({ ...value, instrument: e.target.value || undefined })}
        placeholder="Instrument (e.g. NQ)"
        className="h-9 w-[160px]"
        aria-label="Filter missed by instrument"
      />

      {active && (
        <Button variant="ghost" size="sm" className="h-9" onClick={() => onChange({})}>
          <X className="mr-1 h-3.5 w-3.5" /> Clear
        </Button>
      )}
    </div>
  );
}
