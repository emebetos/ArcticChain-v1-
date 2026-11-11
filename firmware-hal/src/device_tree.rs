//! Live device tree. Every hot-swap bumps `generation` so drivers can detect topology
//! changes without polling individual nodes.

use serde::Serialize;
use std::collections::BTreeMap;
use std::fmt::Write;

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct DtNode {
    pub path: String,
    pub compatible: String,
    pub slot: u8,
    pub uid: u64,
    pub status: String,
    pub props: BTreeMap<String, String>,
}

#[derive(Debug, Clone, Default, Serialize)]
pub struct DeviceTree {
    pub generation: u64,
    pub nodes: BTreeMap<String, DtNode>,
}

impl DeviceTree {
    pub fn insert(&mut self, node: DtNode) {
        self.nodes.insert(node.path.clone(), node);
        self.generation += 1;
    }

    pub fn remove(&mut self, path: &str) -> Option<DtNode> {
        let n = self.nodes.remove(path);
        if n.is_some() {
            self.generation += 1;
        }
        n
    }

    pub fn set(&mut self, path: &str, key: &str, value: impl Into<String>) {
        if let Some(n) = self.nodes.get_mut(path) {
            let v = value.into();
            if n.props.get(key) != Some(&v) {
                n.props.insert(key.to_string(), v);
                self.generation += 1;
            }
        }
    }

    pub fn set_status(&mut self, path: &str, status: &str) {
        if let Some(n) = self.nodes.get_mut(path) {
            if n.status != status {
                n.status = status.to_string();
                self.generation += 1;
            }
        }
    }

    pub fn by_slot(&self, slot: u8) -> Option<&DtNode> {
        self.nodes.values().find(|n| n.slot == slot)
    }

    /// Render in devicetree source syntax.
    pub fn to_dts(&self) -> String {
        let mut s = String::new();
        let _ = writeln!(s, "/dts-v1/;\n/* generation {} */\n/ {{\n\tspine {{\n\t\tcompatible = \"arcticchain,ti-spine-v1\";", self.generation);
        for n in self.nodes.values() {
            let name = n.path.rsplit('/').next().unwrap_or("");
            let _ = writeln!(s, "\t\tdock@{} {{\n\t\t\t{} {{", n.slot, name);
            let _ = writeln!(s, "\t\t\t\tcompatible = \"{}\";\n\t\t\t\tstatus = \"{}\";", n.compatible, n.status);
            for (k, v) in &n.props {
                let _ = writeln!(s, "\t\t\t\t{k} = <{v}>;");
            }
            let _ = writeln!(s, "\t\t\t}};\n\t\t}};");
        }
        s.push_str("\t};\n};\n");
        s
    }
}
