import init, { Simulator } from './wasm/monolith_engine.js'

export type Sim = Simulator

export async function loadEngine(): Promise<Simulator> {
  await init()
  const sim = new Simulator()
  // default loadout matches the CAD assembly
  const cfg: [number, string][] = [[0, 'camera'], [1, 'projector'], [2, 'npu'], [3, 'satcom'], [4, 'battery'], [5, 'battery']]
  for (const [slot, cls] of cfg) sim.attach(slot, cls, 'none')
  sim.drain_events()
  return sim
}

export const j = (s: string) => JSON.parse(s)

export const CLASSES = ['battery', 'npu', 'camera', 'satcom', 'projector', 'mesh-radio']
export const CLASS_COLORS: Record<string, string> = {
  BatteryBlock: '#3fb37f', NeuromorphicCore: '#9b6cff', CameraSensor: '#5d6b7a',
  SatelliteTransceiver: '#3f7fd9', ProjectorEngine: '#e0663a', MeshRadio: '#e3b341',
  battery: '#3fb37f', npu: '#9b6cff', camera: '#5d6b7a', satcom: '#3f7fd9', projector: '#e0663a', 'mesh-radio': '#e3b341',
}
export const CLASS_STL: Record<string, string> = {
  BatteryBlock: 'battery', NeuromorphicCore: 'npu', CameraSensor: 'camera',
  SatelliteTransceiver: 'satcom', ProjectorEngine: 'projector', MeshRadio: 'satcom',
}
