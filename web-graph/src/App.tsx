import { useState, useEffect, useRef } from 'react'
import cytoscape, { Core, NodeSingular, EventObject } from 'cytoscape'
import { GraphData, GraphNodeData } from './types'

const COLORS = {
  company: '#3b82f6',      // blue
  sector: '#10b981',       // green
  macro_driver: '#f59e0b', // amber
}

const NODE_SIZES = {
  company: 35,
  sector: 50,
  macro_driver: 30,
}

export default function App() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [visibleSectors, setVisibleSectors] = useState<Set<string>>(new Set())
  const [visibleTypes, setVisibleTypes] = useState<Set<string>>(new Set(['company', 'sector', 'macro_driver']))
  const [selectedNode, setSelectedNode] = useState<GraphNodeData | null>(null)
  const cyRef = useRef<Core | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // Load graph data
  useEffect(() => {
    fetch('./graph-data.json')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data: GraphData) => {
        setGraphData(data)
        // Initialize visible sectors to all sectors
        setVisibleSectors(new Set(data.metadata.sectors))
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  // Initialize Cytoscape
  useEffect(() => {
    if (!graphData || !containerRef.current) return

    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 6,
            'font-size': '10px',
            'color': '#f1f5f9',
            'background-color': '#3b82f6',
            'width': 35,
            'height': 35,
            'border-width': 2,
            'border-color': '#1e293b',
          },
        },
        {
          selector: 'node[type="company"]',
          style: {
            'background-color': COLORS.company,
            'width': NODE_SIZES.company,
            'height': NODE_SIZES.company,
          },
        },
        {
          selector: 'node[type="sector"]',
          style: {
            'background-color': COLORS.sector,
            'width': NODE_SIZES.sector,
            'height': NODE_SIZES.sector,
            'font-size': '12px',
            'font-weight': 'bold',
          },
        },
        {
          selector: 'node[type="macro_driver"]',
          style: {
            'background-color': COLORS.macro_driver,
            'width': NODE_SIZES.macro_driver,
            'height': NODE_SIZES.macro_driver,
            'shape': 'diamond',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 1,
            'line-color': '#475569',
            'target-arrow-color': '#475569',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'opacity': 0.6,
          },
        },
        {
          selector: 'edge[type="belongs_to"]',
          style: {
            'line-color': '#10b981',
            'target-arrow-color': '#10b981',
            'width': 2,
          },
        },
        {
          selector: 'edge[type="exposed_to"]',
          style: {
            'line-color': '#f59e0b',
            'target-arrow-color': '#f59e0b',
            'line-style': 'dashed',
          },
        },
        {
          selector: '.highlighted',
          style: {
            'border-width': 4,
            'border-color': '#f1f5f9',
            'opacity': 1,
          },
        },
        {
          selector: '.faded',
          style: {
            'opacity': 0.15,
          },
        },
      ],
      layout: {
        name: 'cose',
        animate: true,
        animationDuration: 500,
        nodeRepulsion: 8000,
        idealEdgeLength: 100,
        nodeOverlap: 20,
      },
    })

    cy.on('tap', 'node', (evt: EventObject) => {
      const node = evt.target as NodeSingular
      const data = node.data() as GraphNodeData
      setSelectedNode(data)
      // Highlight
      cy.elements().removeClass('highlighted faded')
      node.addClass('highlighted')
      node.neighborhood().addClass('highlighted')
      cy.elements().not(node.union(node.neighborhood())).addClass('faded')
    })

    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) {
        setSelectedNode(null)
        cy.elements().removeClass('highlighted faded')
      }
    })

    cyRef.current = cy

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [graphData])

  // Update graph elements when filters change
  useEffect(() => {
    if (!cyRef.current || !graphData) return

    const cy = cyRef.current
    cy.elements().remove()

    const searchLower = searchQuery.toLowerCase().trim()

    const filteredNodes = graphData.nodes.filter(node => {
      const data = node.data
      // Type filter
      if (!visibleTypes.has(data.type)) return false
      // Sector filter (only applies to companies)
      if (data.type === 'company' && data.sector && !visibleSectors.has(data.sector)) return false
      // Search filter
      if (searchLower) {
        const label = (data.label || '').toLowerCase()
        const isin = (data.isin || '').toLowerCase()
        const symbol = (data.nse_symbol || '').toLowerCase()
        const name = (data.company_name || '').toLowerCase()
        if (!label.includes(searchLower) && !isin.includes(searchLower) && !symbol.includes(searchLower) && !name.includes(searchLower)) {
          return false
        }
      }
      return true
    })

    const visibleNodeIds = new Set(filteredNodes.map(n => n.data.id))

    const filteredEdges = graphData.edges.filter(edge => {
      return visibleNodeIds.has(edge.data.source) && visibleNodeIds.has(edge.data.target)
    })

    cy.add([...filteredNodes, ...filteredEdges])
    cy.layout({ name: 'cose', animate: true, animationDuration: 300 }).run()
  }, [graphData, searchQuery, visibleSectors, visibleTypes])

  const toggleSector = (sector: string) => {
    setVisibleSectors(prev => {
      const next = new Set(prev)
      if (next.has(sector)) next.delete(sector)
      else next.add(sector)
      return next
    })
  }

  const toggleType = (type: string) => {
    setVisibleTypes(prev => {
      const next = new Set(prev)
      if (next.has(type)) next.delete(type)
      else next.add(type)
      return next
    })
  }

  if (loading) return <div className="loading">Loading graph data…</div>
  if (error) return <div className="loading">Error: {error}</div>
  if (!graphData) return <div className="loading">No graph data.</div>

  return (
    <>
      <div className="header">
        <h1>InvestorLens — Knowledge Graph</h1>
        <div className="metadata">
          {graphData.metadata.company_count} companies · {graphData.metadata.sector_count} sectors · {graphData.metadata.macro_driver_count} macro drivers · {graphData.metadata.edge_count} edges
        </div>
      </div>
      <div className="main">
        <div className="sidebar">
          <h2>Search</h2>
          <input
            className="search-input"
            type="text"
            placeholder="Name, ISIN, or symbol…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />

          <h2>Node Types</h2>
          <div className="filter-group">
            {[
              { key: 'company', label: 'Companies', count: graphData.metadata.company_count },
              { key: 'sector', label: 'Sectors', count: graphData.metadata.sector_count },
              { key: 'macro_driver', label: 'Macro Drivers', count: graphData.metadata.macro_driver_count },
            ].map(({ key, label, count }) => (
              <label key={key} className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={visibleTypes.has(key)}
                  onChange={() => toggleType(key)}
                />
                <span style={{ color: COLORS[key as keyof typeof COLORS] }}>●</span>
                {label}
                <span className="filter-count">{count}</span>
              </label>
            ))}
          </div>

          <h2>Sectors</h2>
          <div className="filter-group">
            {graphData.metadata.sectors.map(sector => (
              <label key={sector} className="filter-checkbox">
                <input
                  type="checkbox"
                  checked={visibleSectors.has(sector)}
                  onChange={() => toggleSector(sector)}
                />
                {sector}
              </label>
            ))}
          </div>

          <h2>About</h2>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {graphData.metadata.data_status}
          </p>
          <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '8px' }}>
            Generated: {graphData.metadata.generated_at}
          </p>
        </div>

        <div className="graph-container">
          <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

          <div className="legend">
            <div className="legend-item">
              <div className="legend-dot" style={{ background: COLORS.company }} />
              Company
            </div>
            <div className="legend-item">
              <div className="legend-dot" style={{ background: COLORS.sector }} />
              Sector
            </div>
            <div className="legend-item">
              <div className="legend-dot" style={{ background: COLORS.macro_driver }} />
              Macro Driver
            </div>
          </div>

          {selectedNode && (
            <div className="info-panel">
              <button className="close-btn" onClick={() => { setSelectedNode(null); cyRef.current?.elements().removeClass('highlighted faded') }}>×</button>
              <h3>{selectedNode.label}</h3>
              <div className="info-row">
                <span className="info-label">Type</span>
                <span className="info-value">{selectedNode.type.replace('_', ' ')}</span>
              </div>
              {selectedNode.isin && (
                <div className="info-row">
                  <span className="info-label">ISIN</span>
                  <span className="info-value">{selectedNode.isin}</span>
                </div>
              )}
              {selectedNode.nse_symbol && (
                <div className="info-row">
                  <span className="info-label">NSE Symbol</span>
                  <span className="info-value">{selectedNode.nse_symbol}</span>
                </div>
              )}
              {selectedNode.exchange && (
                <div className="info-row">
                  <span className="info-label">Exchange</span>
                  <span className="info-value">{selectedNode.exchange}</span>
                </div>
              )}
              {selectedNode.sector && (
                <div className="info-row">
                  <span className="info-label">Sector</span>
                  <span className="info-value">{selectedNode.sector}</span>
                </div>
              )}
              {selectedNode.observations_count !== undefined && (
                <div className="info-row">
                  <span className="info-label">Observations</span>
                  <span className="info-value">{selectedNode.observations_count}</span>
                </div>
              )}
              {selectedNode.corporate_actions_count !== undefined && (
                <div className="info-row">
                  <span className="info-label">Corp Actions</span>
                  <span className="info-value">{selectedNode.corporate_actions_count}</span>
                </div>
              )}
              {selectedNode.company_count !== undefined && (
                <div className="info-row">
                  <span className="info-label">Companies</span>
                  <span className="info-value">{selectedNode.company_count}</span>
                </div>
              )}
              {selectedNode.category && (
                <div className="info-row">
                  <span className="info-label">Category</span>
                  <span className="info-value">{selectedNode.category}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
