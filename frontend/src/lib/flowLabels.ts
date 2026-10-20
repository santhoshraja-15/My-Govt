import type { TKey, Vars } from "@/lib/i18n";

/** Translated accessible names for React Flow's built-in controls (passed as the `ariaLabelConfig` prop). */
export function flowLabels(t: (k: TKey, v?: Vars) => string) {
  return {
    "node.a11yDescription.default": t("rf.node"),
    "node.a11yDescription.keyboardDisabled": t("rf.nodeKeyboard"),
    "node.a11yDescription.ariaLiveMessage": ({ direction, x, y }: { direction: string; x: number; y: number }) => t("rf.moved", { direction, x: Math.round(x), y: Math.round(y) }),
    "edge.a11yDescription.default": t("rf.edge"),
    "controls.ariaLabel": t("rf.controls"),
    "controls.zoomIn.ariaLabel": t("rf.zoomIn"),
    "controls.zoomOut.ariaLabel": t("rf.zoomOut"),
    "controls.fitView.ariaLabel": t("rf.fit"),
    "controls.interactive.ariaLabel": t("rf.interactive"),
    "minimap.ariaLabel": t("rf.minimap"),
    "handle.ariaLabel": t("rf.handle"),
  };
}
