import { EmergencyPanel } from './EmergencyPanel';
import type { BuildingLayout } from '../types/building';

export function FloodPanel(props: { layout: BuildingLayout; onChange: (layout: BuildingLayout) => void; disabled: boolean }) {
  return <EmergencyPanel {...props} kind="flood" />;
}
