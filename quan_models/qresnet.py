# copy from pytorch-torchvision-models-resnet
import torch.nn as nn
import torch.utils.model_zoo as model_zoo

from . import LIQ
from .tools import get_conv_fc_quan_type

__all__ = [
    "QResNet",
    "qresnet18",
    "qresnet34",
    "qresnet50",
    "qresnet101",
    "qresnet152",
    "QBasicBlock",
    "QBottleneck",
]

model_urls = {
    "resnet18": "https://download.pytorch.org/models/resnet18-5c106cde.pth",
    "resnet34": "https://download.pytorch.org/models/resnet34-333f7ec4.pth",
    "resnet50": "https://download.pytorch.org/models/resnet50-19c8e357.pth",
    "resnet101": "https://download.pytorch.org/models/resnet101-5d3b4d8f.pth",
    "resnet152": "https://download.pytorch.org/models/resnet152-b121ed2d.pth",
}


def conv3x3(in_planes, out_planes, stride=1):
    "3x3 convolution with padding"
    return nn.Conv2d(
        in_planes, out_planes, kernel_size=3, stride=stride, padding=1, bias=False
    )


def qconv3x3(
    in_planes,
    out_planes,
    stride=1,
    bits_weights=32,
    bits_activations=32,
    conv_type=LIQ.QConv2d,
):
    "3x3 convolution with padding"
    return conv_type(
        in_planes,
        out_planes,
        kernel_size=3,
        stride=stride,
        padding=1,
        bias=False,
        bits_weights=bits_weights,
        bits_activations=bits_activations,
    )


class QBasicBlock(nn.Module):
    expansion = 1

    def __init__(
        self,
        inplanes,
        planes,
        stride=1,
        downsample=None,
        bits_weights=32,
        bits_activations=32,
        conv_type=LIQ.QConv2d,
    ):
        super(QBasicBlock, self).__init__()
        self.name = "resnet-basic"
        self.conv1 = qconv3x3(
            inplanes,
            planes,
            stride,
            bits_weights=bits_weights,
            bits_activations=bits_activations,
            conv_type=conv_type,
        )
        self.bn1 = nn.BatchNorm2d(planes)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = qconv3x3(
            planes,
            planes,
            bits_weights=bits_weights,
            bits_activations=bits_activations,
            conv_type=conv_type,
        )
        self.bn2 = nn.BatchNorm2d(planes)
        self.downsample = downsample
        self.stride = stride
        self.block_index = 0

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class QBottleneck(nn.Module):
    expansion = 4

    def __init__(
        self,
        inplanes,
        planes,
        stride=1,
        downsample=None,
        bits_weights=32,
        bits_activations=32,
        conv_type=LIQ.QConv2d,
    ):
        super(QBottleneck, self).__init__()
        self.name = "resnet-bottleneck"
        self.conv1 = conv_type(
            inplanes,
            planes,
            kernel_size=1,
            bias=False,
            bits_weights=bits_weights,
            bits_activations=bits_activations,
        )
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = conv_type(
            planes,
            planes,
            kernel_size=3,
            stride=stride,
            padding=1,
            bias=False,
            bits_weights=bits_weights,
            bits_activations=bits_activations,
        )
        self.bn2 = nn.BatchNorm2d(planes)
        self.conv3 = conv_type(
            planes,
            planes * 4,
            kernel_size=1,
            bias=False,
            bits_weights=bits_weights,
            bits_activations=bits_activations,
        )
        self.bn3 = nn.BatchNorm2d(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample
        self.stride = stride
        self.block_index = 0

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual

        out = self.relu(out)

        return out


class QResNet(nn.Module):
    def __init__(
        self,
        depth,
        num_classes=1000,
        bits_weights=32,
        bits_activations=32,
        quantize_first_last=False,
        quan_type="LIQ",
    ):
        self.inplanes = 64
        super(QResNet, self).__init__()
        if depth < 50:
            block = QBasicBlock
        else:
            block = QBottleneck

        if depth == 18:
            layers = [2, 2, 2, 2]
        elif depth == 34:
            layers = [3, 4, 6, 3]
        elif depth == 50:
            layers = [3, 4, 6, 3]
        elif depth == 101:
            layers = [3, 4, 23, 3]
        elif depth == 152:
            layers = [3, 8, 36, 3]

        conv_type, fc_type = get_conv_fc_quan_type(quan_type)

        if not quantize_first_last:
            self.conv1 = nn.Conv2d(
                3, 64, kernel_size=7, stride=2, padding=3, bias=False
            )
        else:
            self.conv1 = conv_type(
                3,
                64,
                kernel_size=7,
                stride=2,
                padding=3,
                bias=False,
                bits_weights=8,
                bits_activations=32,
            )
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(
            block,
            64,
            layers[0],
            bits_weights=bits_weights,
            bits_activations=bits_activations,
            conv_type=conv_type,
        )
        self.layer2 = self._make_layer(
            block,
            128,
            layers[1],
            stride=2,
            bits_weights=bits_weights,
            bits_activations=bits_activations,
            conv_type=conv_type,
        )
        self.layer3 = self._make_layer(
            block,
            256,
            layers[2],
            stride=2,
            bits_weights=bits_weights,
            bits_activations=bits_activations,
            conv_type=conv_type,
        )
        self.layer4 = self._make_layer(
            block,
            512,
            layers[3],
            stride=2,
            bits_weights=bits_weights,
            bits_activations=bits_activations,
            conv_type=conv_type,
        )
        self.avgpool = nn.AvgPool2d(7, stride=1)
        if not quantize_first_last:
            self.fc = nn.Linear(512 * block.expansion, num_classes)
        else:
            self.fc = fc_type(
                512 * block.expansion, num_classes, bits_weights=8, bits_activations=8
            )

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="relu")
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def _make_layer(
        self,
        block,
        planes,
        blocks,
        stride=1,
        bits_weights=32,
        bits_activations=32,
        conv_type=LIQ.QConv2d,
    ):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                conv_type(
                    self.inplanes,
                    planes * block.expansion,
                    kernel_size=1,
                    stride=stride,
                    bias=False,
                    bits_weights=bits_weights,
                    bits_activations=bits_activations,
                ),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(
            block(
                self.inplanes,
                planes,
                stride,
                downsample,
                bits_weights=bits_weights,
                bits_activations=bits_activations,
                conv_type=conv_type,
            )
        )
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(
                block(
                    self.inplanes,
                    planes,
                    bits_weights=bits_weights,
                    bits_activations=bits_activations,
                    conv_type=conv_type,
                )
            )

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x


def qresnet18(pretrained=False, **kwargs):
    """Constructs a QResNet-18 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = QResNet(depth=18, **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls["resnet18"]))
    return model


def qresnet34(pretrained=False, **kwargs):
    """Constructs a QResNet-34 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = QResNet(depth=34, **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls["resnet34"]))
    return model


def qresnet50(pretrained=False, **kwargs):
    """Constructs a QResNet-50 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = QResNet(depth=50, **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls["resnet50"]))
    return model


def qresnet101(pretrained=False, **kwargs):
    """Constructs a QResNet-101 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = QResNet(depth=101, **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls["resnet101"]))
    return model


def qresnet152(pretrained=False, **kwargs):
    """Constructs a QResNet-152 model.
    Args:
        pretrained (bool): If True, returns a model pre-trained on ImageNet
    """
    model = QResNet(depth=152, **kwargs)
    if pretrained:
        model.load_state_dict(model_zoo.load_url(model_urls["resnet152"]))
    return model
