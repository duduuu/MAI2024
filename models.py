import torch
from torch import nn
import torch.nn.functional as F
import torchvision.models as models
import timm

import config as CFG
    
class SwinV2_s(nn.Module):
    def __init__(self):
        super(SwinV2_s, self).__init__()
        
        self.model = models.swin_v2_s(pretrained=True)
        self.model.head = nn.Identity()
        self.dropouts = nn.ModuleList([nn.Dropout(0.5) for _ in range(5)])
        self.linear = nn.Linear(768, CFG.gene_size)
        
    def forward(self, x):
        x = self.model(x)
        x = torch.mean(torch.stack([dropout(x) for dropout in self.dropouts]), dim=0)
        x = self.linear(x)
        
        return x
    
class SwinV2_t(nn.Module):
    def __init__(self):
        super(SwinV2_s, self).__init__()
        
        self.model = models.swin_v2_t(pretrained=True)
        self.model.head = nn.Identity()
        self.dropouts = nn.ModuleList([nn.Dropout(0.5) for _ in range(5)])
        self.linear = nn.Linear(768, CFG.gene_size)
        
    def forward(self, x):
        x = self.model(x)
        x = torch.mean(torch.stack([dropout(x) for dropout in self.dropouts]), dim=0)
        x = self.linear(x)
        
        return x
    
class Bleep_SwinV2_s(nn.Module):
    def __init__(self):
        super().__init__()
        self.image_encoder = models.swin_v2_s(pretrained=True)
        self.image_projection = ProjectionHead(embedding_dim=768)
        self.spot_projection = ProjectionHead(embedding_dim=CFG.gene_size)
        
    def cross_entropy(preds, targets, reduction='none'):
        log_softmax = nn.LogSoftmax(dim = -1)
        loss = (-targets * log_softmax(preds)).sum(1)
        if reduction == "none":
            return loss
        elif reduction == "mean":
            return loss.mean()

    def forward(self, batch):
        # Getting Image and spot Features
        image_features = self.image_encoder(batch["image"])
        spot_features = batch["reduced_expression"]
        
        # Getting Image and Spot Embeddings (with same dimension) 
        image_embeddings = self.image_projection(image_features)
        spot_embeddings = self.spot_projection(spot_features)

        # Calculating the Loss
        logits = spot_embeddings @ image_embeddings.T
        images_similarity = image_embeddings @ image_embeddings.T
        spots_similarity = spot_embeddings @ spot_embeddings.T
        targets = F.softmax((images_similarity + spots_similarity) / 2, dim=-1)   
        spots_loss = self.cross_entropy(logits, targets, reduction='none')
        images_loss = self.cross_entropy(logits.T, targets.T, reduction='none')
        loss =  (images_loss + spots_loss) / 2.0 # shape: (batch_size)
        return loss.mean()
    
class ProjectionHead(nn.Module):
    def __init__(self, embedding_dim, projection_dim=256, dropout=0.1):
        super().__init__()
        self.projection = nn.Linear(embedding_dim, projection_dim)
        self.gelu = nn.GELU()
        self.fc = nn.Linear(projection_dim, projection_dim)
        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(projection_dim)
    
    def forward(self, x):
        projected = self.projection(x)
        x = self.gelu(projected)
        x = self.fc(x)
        x = self.dropout(x)
        x = x + projected
        x = self.layer_norm(x)
        return x