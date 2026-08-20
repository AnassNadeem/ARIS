import { apiGet, peekGet } from "../api/client";
import {
  constructorStandingsSchema,
  driverStandingsSchema,
  type ConstructorStandings,
  type DriverStandings,
} from "../api/types";
import { useAsync } from "./useAsync";

export function useStandings(year: number) {
  const driversPath = `/api/standings/drivers/${year}`;
  const constructorsPath = `/api/standings/constructors/${year}`;
  const drivers = useAsync(
    () =>
      apiGet<DriverStandings>(driversPath, {
        schema: driverStandingsSchema,
        timeout: 60_000,
      }),
    [year],
    true,
    () => peekGet<DriverStandings>(driversPath),
  );
  const constructors = useAsync(
    () =>
      apiGet<ConstructorStandings>(constructorsPath, {
        schema: constructorStandingsSchema,
        timeout: 60_000,
      }),
    [year],
    true,
    () => peekGet<ConstructorStandings>(constructorsPath),
  );
  return { drivers, constructors };
}
