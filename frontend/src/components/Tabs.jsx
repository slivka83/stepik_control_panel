export default function Tabs({ items, active, onChange }) {
  return (
    <div className="inline-flex self-start gap-2 pb-0 shrink-0">
      {items.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onChange(tab.key)}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            active === tab.key
              ? 'border-cyber-blue text-cyber-blue'
              : 'border-transparent text-gray-400 hover:text-gray-300'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
