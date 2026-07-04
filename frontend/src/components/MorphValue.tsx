import { memo, useEffect, useRef, useState } from 'react';

const MORPH_DURATION_MS = 150;
const MIN_MORPH_INTERVAL_MS = 420;

export const MorphValue = memo(function MorphValue({ value, className = '' }: { value: string; className?: string }) {
  const previousRef = useRef(value);
  const lastMorphAtRef = useRef(0);
  const [display, setDisplay] = useState({
    previous: value,
    current: value,
    morphing: false,
  });

  useEffect(() => {
    const previous = previousRef.current;
    if (previous === value) return;
    previousRef.current = value;
    const now = performance.now();
    if (now - lastMorphAtRef.current < MIN_MORPH_INTERVAL_MS) {
      setDisplay({ previous: value, current: value, morphing: false });
      return;
    }
    lastMorphAtRef.current = now;
    setDisplay({ previous, current: value, morphing: true });
    const timer = window.setTimeout(() => {
      setDisplay({ previous: value, current: value, morphing: false });
    }, MORPH_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [value]);

  return (
    <span className={['text-morph', className, display.morphing ? 'is-morphing' : ''].filter(Boolean).join(' ')}>
      {display.morphing && <span className="text-morph-old" aria-hidden="true">{display.previous}</span>}
      <span className="text-morph-new">{display.current}</span>
    </span>
  );
});
