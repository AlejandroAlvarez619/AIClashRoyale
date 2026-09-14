from ultralytics import YOLO
import torch

if __name__ == "__main__":
    # For fresh restart, use yolo11s.pt(small)  also require GPU training
    model = YOLO("best_14-new.pt")
    # model = YOLO("yolo11s.pt")


    if not torch.cuda.is_available():
        print("---GPU not available---")
        print("---Running Training on CPU (Please change to GPU if possible)---")
        if input("are you sure you want to train on CPU? If so: type 'y': ") == "y":
            model.train(
                data="dataset/data.yaml",
                epochs=50,
                imgsz=640,
                workers=2,
                batch=8,
                patience=50,
                name="clash_royale_troops_identifier"
            )

    else:
        print("---GPU available---")
        print("---Running Training on GPU (first recognized)---")
        print("---Device name: "+torch.cuda.get_device_name(0)+"---")

        if input("Start training? If so: type 'y': ") == "y":
            model.train(
                data="dataset/data.yaml",
                epochs=100,
                imgsz=640,
                workers=2,
                batch=8,
                patience=50,
                device='cuda',
                name="clash_royale_troops_identifier"
            )