import onnx
import onnx.helper as helper
import numpy as np

def transform_onnx_for_deepstream(input_path, output_path):
    print(f"📦 Loading YOLO ONNX: {input_path}")
    model = onnx.load(input_path)
    graph = model.graph
    
    # 1. FIND THE REAL OUTPUT
    main_output = [o for o in graph.output if not o.name == 'ds_output'][0]
    output_name = main_output.name
    
    # Get shape info [3, 300, 6]
    shape = [d.dim_value for d in main_output.type.tensor_type.shape.dim]
    print(f"🔍 Found original output: {output_name} with shape: {shape}")

    # 2. CLEANUP
    patch_prefix = "DS_"
    nodes_to_keep = [n for n in graph.node if not n.name.startswith(patch_prefix) and 'ds_output' not in n.output]
    graph.ClearField("node")
    graph.node.extend(nodes_to_keep)
    init_to_keep = [i for i in graph.initializer if not i.name.startswith(patch_prefix)]
    graph.ClearField("initializer")
    graph.initializer.extend(init_to_keep)
    graph.ClearField("output")

    # 3. ADD TRANSFORMATION NODES
    nodes = []
    graph.initializer.append(helper.make_tensor(patch_prefix + 'axis_2', onnx.TensorProto.INT64, [1], [2]))
    
    def add_slice(name, start, end):
        s_name = patch_prefix + 's_' + name
        e_name = patch_prefix + 'e_' + name
        graph.initializer.append(helper.make_tensor(s_name, onnx.TensorProto.INT64, [1], [start]))
        graph.initializer.append(helper.make_tensor(e_name, onnx.TensorProto.INT64, [1], [end]))
        nodes.append(helper.make_node('Slice', inputs=[output_name, s_name, e_name, patch_prefix + 'axis_2'], outputs=[patch_prefix + name], name=patch_prefix + 'Slice_' + name))

    # Slice the coordinates
    add_slice('x1', 0, 1)
    add_slice('y1', 1, 2)
    add_slice('x2', 2, 3)
    add_slice('y2', 3, 4)
    add_slice('score', 4, 5)
    add_slice('label', 5, 6)

    # FILTER: Only keep Person (Class 0)
    # We create a mask: (label == 0)
    graph.initializer.append(helper.make_tensor(patch_prefix + 'zero', onnx.TensorProto.FLOAT, [1], [0.0]))
    nodes.append(helper.make_node('Equal', [patch_prefix + 'label', patch_prefix + 'zero'], [patch_prefix + 'is_person_mask'], name=patch_prefix + 'MaskGen'))
    nodes.append(helper.make_node('Cast', [patch_prefix + 'is_person_mask'], [patch_prefix + 'is_person_float'], to=onnx.TensorProto.FLOAT, name=patch_prefix + 'MaskCast'))
    
    # Zero out scores for non-people
    nodes.append(helper.make_node('Mul', [patch_prefix + 'score', patch_prefix + 'is_person_float'], [patch_prefix + 'filtered_score'], name=patch_prefix + 'ScoreFilter'))

    # Final Concat
    nodes.append(helper.make_node(
        'Concat', 
        inputs=[patch_prefix + 'x1', patch_prefix + 'y1', patch_prefix + 'x2', patch_prefix + 'y2', patch_prefix + 'filtered_score', patch_prefix + 'label'], 
        outputs=['ds_output'], 
        axis=2,
        name=patch_prefix + 'FinalConcat'
    ))

    graph.node.extend(nodes)
    graph.output.append(helper.make_tensor_value_info('ds_output', onnx.TensorProto.FLOAT, [shape[0], shape[1], 6]))

    print(f"🚀 Model patched. Only Person (Class 0) will be detected. Final shape: {shape}")
    onnx.save(model, output_path)

if __name__ == "__main__":
    transform_onnx_for_deepstream("deepstream/yolo26l.onnx", "deepstream/yolo26l.onnx")
