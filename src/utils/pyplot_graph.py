from pyvis.network import Network

# Initialize the Pyvis network with a fixed notebook view
net = Network(height='600px', width='100%', notebook=False, directed=True)

nodes = [
    # (node_id, label, title, color, size)
    ("Microstructure", "Microstructure", "Top-level microstructural entity", "#FF5733", 30),
    ("Pileup", "Pileup", "Localized group of dislocations", "#33FF57", 25),
    ("Dislocation", "Dislocation", "Individual line defect", "#3357FF", 25),
    ("SlipTrace", "SlipTrace", "Lines indicating slip direction", "#F1C40F", 25),
]

for node_id, label, title, color, size in nodes:
    net.add_node(
        node_id,
        label=label,
        title=title,
        shape='dot',
        size=size,
        color=color,
        font={'size': 16, 'face': 'arial'}
    )

edges = [
    ("Microstructure", "Pileup", "HAS_PILEUP"),
    ("Pileup", "Dislocation", "CONTAINS"),
    ("Dislocation", "Dislocation", "NEIGHBOR"),
    ("Pileup", "SlipTrace", "HAS_SLIP_TRACE"),
    ("Microstructure", "SlipTrace", "HAS_SLIP_TRACE"),
]

for source, target, relation in edges:
    net.add_edge(
        source,
        target,
        label=relation,
        title=relation,
        length=300  # Increase this value if more spacing is needed
    )

net.set_options("""
var options = {
  "physics": {
    "barnesHut": {
      "springLength": 300,
      "gravitationalConstant": -8000
    }
  }
}
""")

# Generate and save the interactive graph
html_path = 'assets/network.html'
net.save_graph(html_path)
