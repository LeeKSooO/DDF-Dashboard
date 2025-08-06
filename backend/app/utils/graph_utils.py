import numpy as np
import pandas as pd
import os
from typing import Optional, List
from pathlib import Path
import pickle
from loguru import logger
from scipy.linalg import eigh

def load_chebyshev_polynomials(
    model_base_path: str,
    num_vertices: int,
    k_order: int = 3
) -> Optional[np.ndarray]:
    """
    Load pre-computed Chebyshev polynomials for the graph
    
    Args:
        model_base_path: Base path where model files are stored
        num_vertices: Number of vertices in the graph
        k_order: Order of Chebyshev polynomials
        
    Returns:
        Chebyshev polynomials as numpy array or None if not found
    """
    try:
        cheb_path = os.path.join(model_base_path, "chebyshev_polynomials.pkl")
        
        if os.path.exists(cheb_path):
            with open(cheb_path, 'rb') as f:
                cheb_polynomials = pickle.load(f)
            
            logger.info(f"Loaded Chebyshev polynomials from {cheb_path}")
            return cheb_polynomials
        else:
            logger.warning(f"Chebyshev polynomials not found at {cheb_path}")
            # Generate identity matrix as fallback
            return generate_identity_polynomials(num_vertices, k_order)
            
    except Exception as e:
        logger.error(f"Failed to load Chebyshev polynomials: {e}")
        return generate_identity_polynomials(num_vertices, k_order)

def generate_identity_polynomials(num_vertices: int, k_order: int) -> np.ndarray:
    """
    Generate identity matrix-based polynomials as fallback
    
    Args:
        num_vertices: Number of vertices
        k_order: Order of polynomials
        
    Returns:
        Identity-based polynomials
    """
    logger.info(f"Generating identity polynomials for {num_vertices} vertices, order {k_order}")
    
    # Create identity matrix for each order
    polynomials = np.zeros((k_order, num_vertices, num_vertices))
    
    # T_0 = I (identity)
    polynomials[0] = np.eye(num_vertices)
    
    if k_order > 1:
        # T_1 = L (for identity, this is also identity)
        polynomials[1] = np.eye(num_vertices)
    
    # Higher order terms (T_k = 2*L*T_{k-1} - T_{k-2})
    for k in range(2, k_order):
        polynomials[k] = 2 * polynomials[1] @ polynomials[k-1] - polynomials[k-2]
    
    return polynomials

def load_adjacency_matrix(file_path: str) -> Optional[np.ndarray]:
    """
    Load adjacency matrix from file
    
    Args:
        file_path: Path to adjacency matrix file
        
    Returns:
        Adjacency matrix or None if not found
    """
    try:
        if file_path.endswith('.csv'):
            adj_matrix = pd.read_csv(file_path, header=None).values
        elif file_path.endswith('.npy'):
            adj_matrix = np.load(file_path)
        elif file_path.endswith('.pkl'):
            with open(file_path, 'rb') as f:
                adj_matrix = pickle.load(f)
        else:
            logger.error(f"Unsupported file format: {file_path}")
            return None
        
        logger.info(f"Loaded adjacency matrix from {file_path}, shape: {adj_matrix.shape}")
        return adj_matrix
        
    except Exception as e:
        logger.error(f"Failed to load adjacency matrix from {file_path}: {e}")
        return None

def compute_chebyshev_polynomials(
    adj_matrix: np.ndarray,
    k_order: int = 3
) -> np.ndarray:
    """
    Compute Chebyshev polynomials from adjacency matrix
    
    Args:
        adj_matrix: Adjacency matrix
        k_order: Order of Chebyshev polynomials
        
    Returns:
        Chebyshev polynomials
    """
    try:
        num_vertices = adj_matrix.shape[0]
        
        # Compute degree matrix
        degree = np.sum(adj_matrix, axis=1)
        degree_matrix = np.diag(degree)
        
        # Compute normalized Laplacian: L = I - D^(-1/2) * A * D^(-1/2)
        degree_inv_sqrt = np.diag(1.0 / np.sqrt(degree + 1e-8))  # Add small epsilon to avoid division by zero
        normalized_adj = degree_inv_sqrt @ adj_matrix @ degree_inv_sqrt
        laplacian = np.eye(num_vertices) - normalized_adj
        
        # Scale Laplacian eigenvalues to [-1, 1]
        eigenvals, _ = eigh(laplacian)
        lambda_max = np.max(eigenvals)
        scaled_laplacian = (2.0 / lambda_max) * laplacian - np.eye(num_vertices)
        
        # Compute Chebyshev polynomials
        polynomials = np.zeros((k_order, num_vertices, num_vertices))
        
        # T_0 = I
        polynomials[0] = np.eye(num_vertices)
        
        if k_order > 1:
            # T_1 = L
            polynomials[1] = scaled_laplacian
        
        # Recurrence relation: T_k = 2*L*T_{k-1} - T_{k-2}
        for k in range(2, k_order):
            polynomials[k] = 2 * scaled_laplacian @ polynomials[k-1] - polynomials[k-2]
        
        logger.info(f"Computed Chebyshev polynomials, shape: {polynomials.shape}")
        return polynomials
        
    except Exception as e:
        logger.error(f"Failed to compute Chebyshev polynomials: {e}")
        raise

def save_chebyshev_polynomials(
    polynomials: np.ndarray,
    save_path: str
) -> bool:
    """
    Save Chebyshev polynomials to file
    
    Args:
        polynomials: Chebyshev polynomials
        save_path: Path to save file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'wb') as f:
            pickle.dump(polynomials, f)
        
        logger.info(f"Saved Chebyshev polynomials to {save_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save Chebyshev polynomials: {e}")
        return False

def create_graph_from_coordinates(
    coordinates: List[tuple],
    distance_threshold: float = 1000.0
) -> np.ndarray:
    """
    Create adjacency matrix from coordinates using distance threshold
    
    Args:
        coordinates: List of (lat, lon) tuples
        distance_threshold: Distance threshold in meters
        
    Returns:
        Adjacency matrix
    """
    try:
        num_stops = len(coordinates)
        adj_matrix = np.zeros((num_stops, num_stops))
        
        for i in range(num_stops):
            for j in range(i + 1, num_stops):
                # Calculate Haversine distance
                distance = haversine_distance(
                    coordinates[i][0], coordinates[i][1],
                    coordinates[j][0], coordinates[j][1]
                )
                
                if distance <= distance_threshold:
                    adj_matrix[i, j] = 1.0
                    adj_matrix[j, i] = 1.0  # Symmetric
        
        logger.info(f"Created adjacency matrix from coordinates, shape: {adj_matrix.shape}")
        logger.info(f"Number of edges: {np.sum(adj_matrix) / 2}")
        
        return adj_matrix
        
    except Exception as e:
        logger.error(f"Failed to create graph from coordinates: {e}")
        raise

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate Haversine distance between two points in meters
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
        
    Returns:
        Distance in meters
    """
    R = 6371000  # Earth's radius in meters
    
    # Convert to radians
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2)
    lon2_rad = np.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = np.sin(dlat/2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    return R * c