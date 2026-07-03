import { memo, useEffect, useRef, useState } from 'react';

const MORPH_DURATION_MS = 360;

export const MorphValue = memo(function MorphValue({ value, className = '' }: { value: string; className?: string }) {
  const previousRef = useRef(value);
  const [previous, setPrevious] = useState<string | null>(null);
  const [morphing, setMorphing] = useState(false);

  useEffect(() => {
    if (previousRef.current === value) return;
    setPrevious(previousRef.current);
    previousRef.current = value;
    setMorphing(true);
    const timer = window.setTimeout(() => {
      setMorphing(false);
      setPrevious(null);
    }, MORPH_DURATION_MS);
    return () => window.clearTimeout(timer);
  }, [value]);

  return (
    <span className={['text-morph', className, morphing ? 'is-morphing' : ''].filter(Boolean).join(' ')}>
      {previous != null && <span className="text-morph-old" aria-hidden="true">{previous}</span>}
      <span className="text-morph-new">{value}</span>
    </span>
  );
});
