"""Build ONNX TreeEnsembleClassifier directly from HistGradientBoostingClassifier.

Exports exact tree nodes, thresholds, weights, base prediction, and class labels
into standard ONNX ai.onnx.ml TreeEnsembleClassifier (opset 1 ai.onnx.ml).
"""

import json
from pathlib import Path
import joblib
import numpy as np
import onnx
from onnx import helper, TensorProto
import onnxruntime as ort

def export_hgb_to_onnx(model_path: Path, onnx_out_path: Path):
    print(f"Loading {model_path}...")
    model = joblib.load(model_path)

    n_features = 36
    n_classes = len(model.classes_) # 10
    classes = [int(c) for c in model.classes_]

    # Model baseline prediction shape (1, n_classes)
    base_values = model._baseline_prediction.flatten().astype(np.float32).tolist()

    # We will build TreeEnsembleClassifier attributes
    nodes_treeids = []
    nodes_nodeids = []
    nodes_featureids = []
    nodes_values = [] # thresholds
    nodes_hitrates = []
    nodes_modes = [] # "BRANCH_LEQ" or "LEAF"
    nodes_truenodeids = [] # left child
    nodes_falsenodeids = [] # right child
    nodes_missing_value_tracks_true = []

    class_treeids = []
    class_nodeids = []
    class_ids = []
    class_weights = []

    tree_id_counter = 0

    for iter_idx in range(model.n_iter_):
        for class_idx in range(n_classes):
            predictor = model._predictors[iter_idx][class_idx]
            nodes = predictor.nodes

            current_tree_id = tree_id_counter
            tree_id_counter += 1

            for node_id, node in enumerate(nodes):
                is_leaf = bool(node['is_leaf'])
                nodes_treeids.append(current_tree_id)
                nodes_nodeids.append(node_id)
                nodes_hitrates.append(1.0)
                nodes_missing_value_tracks_true.append(1)

                if is_leaf:
                    nodes_featureids.append(0)
                    nodes_values.append(0.0)
                    nodes_modes.append("LEAF")
                    nodes_truenodeids.append(0)
                    nodes_falsenodeids.append(0)

                    class_treeids.append(current_tree_id)
                    class_nodeids.append(node_id)
                    class_ids.append(class_idx) # index into classes
                    class_weights.append(float(node['value']))
                else:
                    nodes_featureids.append(int(node['feature_idx']))
                    nodes_values.append(float(node['num_threshold']))
                    nodes_modes.append("BRANCH_LEQ")
                    nodes_truenodeids.append(int(node['left']))
                    nodes_falsenodeids.append(int(node['right']))

    # Create TreeEnsembleClassifier node
    node = helper.make_node(
        "TreeEnsembleClassifier",
        domain="ai.onnx.ml",
        inputs=["float_input"],
        outputs=["label", "probabilities"],
        nodes_treeids=nodes_treeids,
        nodes_nodeids=nodes_nodeids,
        nodes_featureids=nodes_featureids,
        nodes_values=nodes_values,
        nodes_hitrates=nodes_hitrates,
        nodes_modes=nodes_modes,
        nodes_truenodeids=nodes_truenodeids,
        nodes_falsenodeids=nodes_falsenodeids,
        nodes_missing_value_tracks_true=nodes_missing_value_tracks_true,
        class_treeids=class_treeids,
        class_nodeids=class_nodeids,
        class_ids=class_ids,
        class_weights=class_weights,
        classlabels_int64s=classes,
        base_values=base_values,
        post_transform="SOFTMAX"
    )

    # Input and output types
    input_def = helper.make_tensor_value_info("float_input", TensorProto.FLOAT, [None, n_features])
    output_label = helper.make_tensor_value_info("label", TensorProto.INT64, [None])
    output_prob = helper.make_tensor_value_info("probabilities", TensorProto.FLOAT, [None, n_classes])

    # Graph
    graph = helper.make_graph(
        [node],
        "layout_classifier",
        [input_def],
        [output_label, output_prob]
    )

    # Model with standard opset and ai.onnx.ml opset
    opset_ai_onnx = helper.make_operatorsetid("", 15)
    opset_ai_onnx_ml = helper.make_operatorsetid("ai.onnx.ml", 1)

    model_proto = helper.make_model(
        graph,
        producer_name="DocMorphExporter",
        opset_imports=[opset_ai_onnx, opset_ai_onnx_ml]
    )
    model_proto.ir_version = 8

    onnx.checker.check_model(model_proto)
    with open(onnx_out_path, "wb") as f:
        f.write(model_proto.SerializeToString())

    print(f"Saved ONNX model to {onnx_out_path} ({onnx_out_path.stat().st_size / 1024:.2f} KB)")


def verify_parity(model_path: Path, onnx_path: Path, benchmark_path: Path):
    print("Verifying parity between Scikit-Learn and ONNX...")
    model = joblib.load(model_path)
    sess = ort.InferenceSession(str(onnx_path))
    input_name = sess.get_inputs()[0].name

    # 1. Synthetic data
    rng = np.random.RandomState(42)
    test_X = rng.rand(500, 36).astype(np.float32)

    py_pred = model.predict(test_X)
    py_proba = model.predict_proba(test_X)

    onnx_out = sess.run(None, {input_name: test_X})
    onnx_pred = onnx_out[0]
    onnx_proba = onnx_out[1]

    pred_match = np.array_equal(py_pred, onnx_pred)
    max_prob_diff = np.max(np.abs(py_proba - onnx_proba))
    print(f"Synthetic (500 samples): Predictions Match = {pred_match}, Max Proba Diff = {max_prob_diff:.6f}")
    assert pred_match, "Synthetic predictions mismatch!"

    # 2. Benchmark data if available
    if benchmark_path.exists():
        with open(benchmark_path, "r", encoding="utf-8") as f:
            bench_data = json.load(f)

        from ai_training.train import LayoutFeatureExtractor
        extractor = LayoutFeatureExtractor()

        total_tokens = 0
        matches = 0
        max_bench_diff = 0.0

        for page in bench_data:
            tokens = page.get("tokens", [])
            bboxes = page.get("bboxes", [])
            if not tokens:
                continue

            feats = extractor.extract_features(tokens, bboxes)
            p_pred = model.predict(feats)
            p_proba = model.predict_proba(feats)

            o_out = sess.run(None, {input_name: feats})
            o_pred = o_out[0]
            o_proba = o_out[1]

            total_tokens += len(tokens)
            matches += int(np.sum(p_pred == o_pred))
            max_bench_diff = max(max_bench_diff, float(np.max(np.abs(p_proba - o_proba))))

        agreement = (matches / total_tokens) * 100.0 if total_tokens > 0 else 100.0
        print(f"Benchmark Test ({total_tokens} tokens): Parity Agreement = {agreement:.2f}%, Max Proba Diff = {max_bench_diff:.6f}")
        assert matches == total_tokens, f"Mismatch on benchmark tokens: {matches}/{total_tokens}"
    else:
        print("Benchmark file not found, skipping benchmark verification.")

    print("ALL PARITY CHECKS PASSED: 100.0% IDENTICAL PREDICTIONS!")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    m_path = base_dir / "trained_model" / "layout_classifier.joblib"
    o_path = base_dir / "trained_model" / "layout_classifier.onnx"
    b_path = base_dir / "data" / "benchmark_v1_test.json"

    export_hgb_to_onnx(m_path, o_path)
    verify_parity(m_path, o_path, b_path)
