import { Chart, registerables } from 'chart.js';
Chart.register(...registerables);
export const WCOL = { A: '#2f6f9f', B: '#2e8b6a', C: '#8a5fb0' };
export const Chip = ({ w }) => w ? <span className={`chip chip${w}`}>{w}</span> : <span className="chip chipN">unserved</span>;
export const fmt = (m, s, d = 1) => (s === undefined ? (+m).toFixed(d) : `${(+m).toFixed(d)} ± ${(+s).toFixed(d)}`);
export const dayClass = (d) => (d <= 0 ? 'bad' : d <= 30 ? 'warnt' : '');
