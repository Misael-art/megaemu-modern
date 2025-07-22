import { useRef, useState } from 'react';

export function useUndoRedo<T>(initialState: T) {
  const [state, setState] = useState<T>(initialState);
  const history = useRef<T[]>([initialState]);
  const index = useRef<number>(0);

  const set = (newState: T) => {
    index.current += 1;
    history.current = [...history.current.slice(0, index.current), newState];
    setState(newState);
  };

  const undo = () => {
    if (index.current > 0) {
      index.current -= 1;
      setState(history.current[index.current]);
    }
  };

  const redo = () => {
    if (index.current < history.current.length - 1) {
      index.current += 1;
      setState(history.current[index.current]);
    }
  };

  return { state, set, undo, redo };
}