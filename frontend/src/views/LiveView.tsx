import { HomeView } from "./HomeView";
import type { CalendarRound, CalendarState } from "../api/types";

export function LiveView({
  year,
  calendarState,
  rounds,
  onReplay,
  onEnterLive,
}: {
  year: number;
  calendarState?: CalendarState;
  rounds: CalendarRound[];
  onReplay: (r: CalendarRound, year: number) => void;
  onEnterLive: () => void;
}) {
  return (
    <HomeView
      year={year}
      calendarState={calendarState}
      rounds={rounds}
      onReplay={onReplay}
      onLive={onEnterLive}
      onStandings={() => undefined}
      onRetry={() => undefined}
      loading={false}
    />
  );
}
