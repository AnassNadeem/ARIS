import { apiGet } from "../api/client";
import { driversSchema, type DriversResponse } from "../api/types";
import { useAsync } from "./useAsync";

export function useDrivers(year: number) {
  return useAsync(
    () => apiGet<DriversResponse>(`/api/drivers/${year}`, { schema: driversSchema, timeout: 30_000 }),
    [year],
  );
}
