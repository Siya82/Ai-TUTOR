// Load a /console path, with reload (ADR-051).
import { useCallback, useEffect, useState } from "react";
import { call } from "./api";

export function useLoad(path, token) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const reload = useCallback(async () => {
    try {
      setData(await call(path, { token }));
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, [path, token]);
  useEffect(() => {
    const id = setTimeout(reload, 0);
    return () => clearTimeout(id);
  }, [reload]);
  return { data, error, reload, setData };
}
