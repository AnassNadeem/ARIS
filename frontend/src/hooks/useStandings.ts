import { apiGet } from "../api/client";
import {
  constructorStandingsSchema,
  driverStandingsSchema,
  type ConstructorStandings,
  type DriverStandings,
} from "../api/types";
import { useAsync } from "./useAsync";

export function useStandings(year: number) {
  const drivers = useAsync(
    () =>
      apiGet<DriverStandings>(`/api/standings/drivers/${year}`, {
        schema: driverStandingsSchema,
        timeout: 60_000,
      }),
    [year],
  );
  const constructors = useAsync(
    () =>
      apiGet<ConstructorStandings>(`/api/standings/constructors/${year}`, {
        schema: constructorStandingsSchema,
        timeout: 60_000,
      }),
    [year],
  );
  return { drivers, constructors };
}
