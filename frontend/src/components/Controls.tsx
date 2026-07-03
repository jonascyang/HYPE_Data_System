import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';

export function SelectControl({
  value,
  options,
  onChange,
  label,
  formatOption = (option) => option,
}: {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  label?: string;
  formatOption?: (value: string) => string;
}) {
  return (
    <DropdownControl
      value={value}
      options={options}
      onChange={onChange}
      label={label}
      formatOption={formatOption}
      className="control select-control"
    />
  );
}

export function DropdownControl({
  value,
  options,
  onChange,
  label,
  formatOption = (option) => option,
  className,
  placeholder = 'All',
}: {
  value: string;
  options: string[];
  onChange: (value: string) => void;
  label?: string;
  formatOption?: (value: string) => string;
  className: string;
  placeholder?: string;
}) {
  const id = useId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const labelId = label ? `${id}-label` : undefined;
  const menuId = `${id}-menu`;
  const renderedOptions = value === '' && !options.includes('') ? ['', ...options] : options;
  const selectedIndex = Math.max(0, renderedOptions.findIndex((option) => option === value));
  const displayValue = value === '' ? placeholder : formatOption(value);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const frame = window.requestAnimationFrame(() => {
      optionRefs.current[activeIndex]?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeIndex, open]);

  const openAt = (index: number) => {
    if (renderedOptions.length === 0) return;
    setActiveIndex(clampIndex(index, renderedOptions.length));
    setOpen(true);
  };

  const selectOption = (option: string) => {
    onChange(option);
    setOpen(false);
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  };

  const onTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      openAt(open ? activeIndex + 1 : selectedIndex);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      openAt(open ? activeIndex - 1 : selectedIndex);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      openAt(selectedIndex);
    }
  };

  const onOptionKeyDown = (event: KeyboardEvent<HTMLButtonElement>, option: string, index: number) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveIndex(clampIndex(index + 1, renderedOptions.length));
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveIndex(clampIndex(index - 1, renderedOptions.length));
    } else if (event.key === 'Home') {
      event.preventDefault();
      setActiveIndex(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      setActiveIndex(renderedOptions.length - 1);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      selectOption(option);
    } else if (event.key === 'Tab') {
      setOpen(false);
    }
  };

  return (
    <div className={`${className} dropdown-control`} ref={rootRef}>
      {label && <span id={labelId}>{label}</span>}
      <div className="dropdown-shell">
        <button
          type="button"
          ref={triggerRef}
          className="dropdown-trigger"
          aria-haspopup="listbox"
          aria-expanded={open}
          aria-controls={open ? menuId : undefined}
          aria-labelledby={labelId}
          aria-label={label ? undefined : 'Select value'}
          disabled={renderedOptions.length === 0}
          onClick={() => {
            if (open) setOpen(false);
            else openAt(selectedIndex);
          }}
          onKeyDown={onTriggerKeyDown}
        >
          <span>{displayValue}</span>
          <span className="dropdown-caret" aria-hidden="true" />
        </button>
        {open && (
          <div className="dropdown-menu" id={menuId} role="listbox" aria-labelledby={labelId}>
            {renderedOptions.map((option, index) => {
              const optionLabel = option === '' ? placeholder : formatOption(option);
              return (
                <button
                  type="button"
                  role="option"
                  aria-selected={option === value}
                  className={option === value ? 'active' : ''}
                  key={option || 'all'}
                  ref={(node) => { optionRefs.current[index] = node; }}
                  onClick={() => selectOption(option)}
                  onKeyDown={(event) => onOptionKeyDown(event, option, index)}
                >
                  {optionLabel}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export function SegmentControl<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: T[];
  onChange: (value: T) => void;
  label?: string;
}) {
  return (
    <div className="segment-control" role="group" aria-label={label ?? 'Segment control'}>
      {options.map((option) => (
        <button
          key={option}
          className={option === value ? 'active' : ''}
          onClick={() => onChange(option)}
          type="button"
          aria-pressed={option === value}
        >
          {formatSegmentOption(option)}
        </button>
      ))}
    </div>
  );
}

function formatSegmentOption(value: string) {
  if (/^\d+$/.test(value)) return `${value}D`;
  if (value === 'total') return 'Total';
  if (value === 'call') return 'Call';
  if (value === 'put') return 'Put';
  return value;
}

function clampIndex(index: number, length: number) {
  if (length <= 0) return 0;
  if (index < 0) return length - 1;
  if (index >= length) return 0;
  return index;
}
