// Graph data types matching the Python builder output

export interface GraphNodeData {
  id: string
  label: string
  type: 'company' | 'sector' | 'macro_driver'
  // Company fields
  sector?: string
  isin?: string
  nse_symbol?: string
  bse_code?: string
  company_name?: string
  exchange?: string
  observations_count?: number
  corporate_actions_count?: number
  // Sector fields
  company_count?: number
  // Macro driver fields
  category?: string
  slug?: string
}

export interface GraphNode {
  data: GraphNodeData
}

export interface GraphEdgeData {
  id: string
  source: string
  target: string
  type: 'belongs_to' | 'exposed_to'
  label: string
}

export interface GraphEdge {
  data: GraphEdgeData
}

export interface GraphMetadata {
  generated_at: string
  node_count: number
  edge_count: number
  company_count: number
  sector_count: number
  macro_driver_count: number
  sectors: string[]
  data_status: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  metadata: GraphMetadata
}
