export type AppRoute = 'market' | 'positionLookup' | 'greekSimulator' | 'strategySimulator';

const NAV_ITEMS: Array<{ route: AppRoute; label: string }> = [
  { route: 'market', label: 'Market Dashboard' },
  { route: 'positionLookup', label: 'Position Lookup' },
  { route: 'greekSimulator', label: 'Greek Simulator' },
  { route: 'strategySimulator', label: 'Strategy Simulator' },
];

export function SideNav({
  route,
  onRouteChange,
}: {
  route: AppRoute;
  onRouteChange: (route: AppRoute) => void;
}) {
  return (
    <nav className="side-nav" aria-label="Primary navigation">
      <div className="side-nav-brand">HYPE</div>
      {NAV_ITEMS.map((item) => (
        <button
          key={item.route}
          type="button"
          className={route === item.route ? 'side-nav-item active' : 'side-nav-item'}
          data-route={item.route}
          onClick={() => onRouteChange(item.route)}
          aria-current={route === item.route ? 'page' : undefined}
        >
          <span className="side-nav-glyph" aria-hidden="true" />
          <span>{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
