import { apiGet, peekGet } from "../api/client";
import { driversSchema, type DriversResponse } from "../api/types";
import { useAsync } from "./useAsync";

export function useDrivers(year: number) {
  const path = `/api/drivers/${year}`;
  return useAsync(
    () => apiGet<DriversResponse>(path, { schema: driversSchema, timeout: 60_000 }),
    [year],
    true,
    () => peekGet<DriversResponse>(path),
  );
}
