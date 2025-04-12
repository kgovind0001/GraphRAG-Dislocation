import json
import glob
from neo4j import GraphDatabase

class DislocationGraph:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_pileup(self, tx, pileup_id, pileup_data):
        query = (
            "MERGE (p:Pileup { id: $pileup_id }) "
            "SET p.pileup_id = $pileup_id, "
            "    p.n_dislocations = $n_dislocations, "
            "    p.start_pos = $start_pos, "
            "    p.slip_width = $slip_width, "
            "    p.offset = $offset, "
            "    p.direction = $direction "
            "RETURN p"
        )
        tx.run(query,
            pileup_id=pileup_id,
            n_dislocations=pileup_data.get("n_dislocations"),
            start_pos=pileup_data.get("start_pos"),
            slip_width=pileup_data.get("slip_width"),
            offset=pileup_data.get("offset"),
            direction=pileup_data.get("direction")
        )

    def create_dislocation(self, tx, pileup_id, dislocation_key, dislocation_data):
        composite_id = f"{pileup_id}_{dislocation_key}"
        query = (
            "MERGE (d:Dislocation { id: $composite_id }) "
            "SET d.dis_id = $composite_id, "
            "    d.spline_id = $spline_id, "
            "    d.start_pos_x = $start_pos_x, "
            "    d.start_pos_y = $start_pos_y, "
            "    d.offset = $offset "
            "WITH d "
            "MATCH (p:Pileup { id: $pileup_id }) "
            "MERGE (p)-[:CONTAINS]->(d) "
            "RETURN d"
        )
        tx.run(query,
            composite_id=composite_id,
            spline_id=dislocation_data.get("spline_id"),
            start_pos_x=dislocation_data.get("start_pos")[0],
            start_pos_y=dislocation_data.get("start_pos")[1],
            offset=dislocation_data.get("offset"), 
            pileup_id=pileup_id
        )
        # Return the composite id so it can be used for neighbor relationships.
        return composite_id

    def create_neighbor_relationship(self, tx, comp_id1, comp_id2):
        # Create bidirectional neighbor relationships.
        query = (
            "MATCH (d1:Dislocation { id: $comp_id1 }), (d2:Dislocation { id: $comp_id2 }) "
            "MERGE (d1)-[:NEIGHBOR]->(d2) "
            "MERGE (d2)-[:NEIGHBOR]->(d1)"
        )
        tx.run(query, comp_id1=comp_id1, comp_id2=comp_id2)

    def create_grain_boundary(self, tx, gb_data, gb_id):
        # Create a grain boundary node with a display_id property.
        query = (
            "MERGE (gb:GrainBoundary { id: $gb_id }) "
            "SET gb.gb_id = $gb_id, "
            "    gb.gb_angle = $gb_angle, "
            "    gb.gb_center = $gb_center, "
            "    gb.lw = $lw "
            "RETURN gb"
        )
        tx.run(query,
            gb_id=gb_id,
            gb_angle=gb_data.get("gb_angle"),
            gb_center=gb_data.get("gb_center"),
            lw=gb_data.get("lw")
        )

    def create_slip_trace(self, tx, st_id):
        # Create a slip trace node with a display_id property.
        query = (
            "MERGE (st:SlipTrace { id: $st_id }) "
            "SET st.slip_id = '<id> ' + $st_id "
            "RETURN st"
        )
        tx.run(query, st_id=st_id)

    def create_microstructure(self, tx, ms_id):
        query = (
            "MERGE (m:Microstructure { id: $ms_id }) "
            "SET m.ms_id = $ms_id "
            "RETURN m"
        )
        tx.run(query, ms_id=ms_id)

    def process_json_file(self, json_file):
        with open(json_file, 'r') as f:
            data = json.load(f)

        ms_id = "ms_" + str(int(json_file.split("/")[-1].split(".")[0].replace("param_img", "")))

        include_gb = data.get("include_gb", False)
        slip_trace_flag = data.get("slip_trace", False)
        gb_data = data.get("grain_boundary", None)

        gb_node_id = "gb_" + ms_id
        st_node_id = "st_" + ms_id

        with self.driver.session() as session:
            with session.begin_transaction() as tx:
                print("Creating Microstructure node")
                self.create_microstructure(tx, ms_id)

                if include_gb and gb_data is not None:
                    print("Creating Grain Boundary node")
                    self.create_grain_boundary(tx, gb_data, gb_node_id)
                    tx.run(
                        "MATCH (m:Microstructure { id: $ms_id }), (gb:GrainBoundary { id: $gb_id }) "
                        "MERGE (m)-[:HAS_GRAIN_BOUNDARY]->(gb)",
                        ms_id=ms_id, gb_id=gb_node_id
                    )

                if slip_trace_flag:
                    print("Creating Slip Trace node")
                    self.create_slip_trace(tx, st_node_id)
                    tx.run(
                        "MATCH (m:Microstructure { id: $ms_id }), (st:SlipTrace { id: $st_id }) "
                        "MERGE (m)-[:HAS_SLIP_TRACE]->(st)",
                        ms_id=ms_id, st_id=st_node_id
                    )

                pileups = data.get("pileup", {})
                for pileup_id, pileup_data in pileups.items():
                    pileup_start_pos = pileup_data.get("start_pos", [9999, 9999])  # Default to high value if missing
                    if not (pileup_start_pos[0] < 450 and pileup_start_pos[1] < 450):
                        continue  # Skip this pileup

                    print(f"Processing pileup {pileup_id}")
                    self.create_pileup(tx, pileup_id, pileup_data)

                    tx.run(
                        "MATCH (m:Microstructure { id: $ms_id }), (p:Pileup { id: $pileup_id }) "
                        "MERGE (m)-[:HAS_PILEUP]->(p)",
                        ms_id=ms_id, pileup_id=pileup_id
                    )

                    dislocations = pileup_data.get("dislocation", {})
                    sorted_keys = sorted(dislocations.keys(), key=lambda k: int(k.split('_')[-1]))
                    composite_ids = []

                    for dkey in sorted_keys:
                        ddata = dislocations[dkey]
                        d_start = ddata.get("start_pos", [9999, 9999])
                        if not (d_start[0] < 450 and d_start[1] < 450):
                            continue  # Skip this dislocation

                        comp_id = self.create_dislocation(tx, pileup_id, dkey, ddata)
                        composite_ids.append(comp_id)

                    for i in range(len(composite_ids) - 1):
                        self.create_neighbor_relationship(tx, composite_ids[i], composite_ids[i + 1])

                    if slip_trace_flag:
                        tx.run(
                            "MATCH (p:Pileup { id: $pileup_id }), (st:SlipTrace { id: $st_id }) "
                            "MERGE (p)-[:HAS_SLIP_TRACE]->(st)",
                            pileup_id=pileup_id, st_id=st_node_id
                        )


if __name__ == "__main__":
    uri = "neo4j://localhost:7687"
    user = "neo4j"
    password = "password"
    
    processor = DislocationGraph(uri, user, password)
    try:
        for filepath in glob.glob("sample_data/*.json"):
            processor.process_json_file(filepath)
    finally:
        processor.close()