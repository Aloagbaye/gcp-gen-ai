import re
from typing import List
from collections import Counter

# Import schema - handle both relative and absolute imports
try:
    from .schema import Chunk, Entity
except ImportError:
    from schema import Chunk, Entity

def extract_entities(chunks: List[Chunk]) -> List[Entity]:
    """
    Extract entities from chunks using simple regex-based approach.
    
    Phase 1: Simple heuristic extraction
    - Capitalized words/phrases (potential proper nouns)
    - Basic deduplication
    - Simple type classification
    
    Phase 2 (future): Use Gemini for better NER
    
    Args:
        chunks: List of Chunk objects
        
    Returns:
        List of unique Entity objects
    """
    if not chunks:
        return []
    
    # Collect all potential entities from all chunks
    entity_candidates = []
    
    for chunk in chunks:
        text = chunk.text
        
        # Pattern 1: Capitalized words (2+ chars, not at start of sentence)
        # Matches: "Google", "Vertex AI", "GCP", etc.
        capitalized = re.findall(r'\b[A-Z][a-zA-Z0-9_-]{1,}\b', text)
        
        # Pattern 2: Multi-word capitalized phrases
        # Matches: "Vertex AI", "Google Cloud", "Machine Learning"
        phrases = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', text)
        
        # Pattern 3: Acronyms (2-5 uppercase letters)
        acronyms = re.findall(r'\b[A-Z]{2,5}\b', text)
        
        # Combine all candidates
        candidates = capitalized + phrases + acronyms
        
        # Filter out common false positives
        stop_words = {
            'The', 'This', 'That', 'These', 'Those', 'A', 'An',
            'And', 'Or', 'But', 'If', 'When', 'Where', 'How', 'Why',
            'What', 'Which', 'Who', 'Whom', 'Whose',
            'I', 'You', 'He', 'She', 'It', 'We', 'They',
            'Is', 'Are', 'Was', 'Were', 'Be', 'Been', 'Being',
            'Have', 'Has', 'Had', 'Do', 'Does', 'Did',
            'Will', 'Would', 'Should', 'Could', 'May', 'Might',
            'Can', 'Must', 'Shall'
        }
        
        # Filter and normalize
        for candidate in candidates:
            # Skip if it's a stop word
            if candidate in stop_words:
                continue
            
            # Skip single letters
            if len(candidate) < 2:
                continue
            
            # Normalize: remove extra spaces, convert to title case
            normalized = ' '.join(candidate.split()).title()
            
            # Skip if too long (likely not an entity)
            if len(normalized) > 50:
                continue
            
            entity_candidates.append(normalized)
    
    # Count occurrences and deduplicate
    entity_counts = Counter(entity_candidates)
    
    # Create Entity objects (keep top entities by frequency)
    # Simple type classification based on patterns
    entities = []
    seen = set()
    
    for entity_name, count in entity_counts.most_common(50):  # Top 50 entities
        if entity_name.lower() in seen:
            continue
        
        seen.add(entity_name.lower())
        
        # Simple type classification
        entity_type = classify_entity_type(entity_name)
        
        entities.append(Entity(
            name=entity_name,
            type=entity_type
        ))
    
    return entities

def classify_entity_type(name: str) -> str:
    """
    Simple heuristic to classify entity type.
    
    Returns:
        Entity type: PERSON, ORGANIZATION, PRODUCT, LOCATION, TECHNOLOGY, OTHER
    """
    name_lower = name.lower()
    
    # Technology/Product patterns
    tech_keywords = ['api', 'sdk', 'cloud', 'platform', 'service', 'engine', 'model', 
                     'system', 'framework', 'library', 'tool', 'software', 'application']
    if any(keyword in name_lower for keyword in tech_keywords):
        return "TECHNOLOGY"
    
    # Organization patterns
    org_keywords = ['inc', 'corp', 'llc', 'ltd', 'company', 'group', 'organization']
    if any(keyword in name_lower for keyword in org_keywords):
        return "ORGANIZATION"
    
    # Location patterns (very basic)
    location_keywords = ['city', 'state', 'country', 'region', 'location']
    if any(keyword in name_lower for keyword in location_keywords):
        return "LOCATION"
    
    # Acronyms (2-5 uppercase) often are organizations or technologies
    if re.match(r'^[A-Z]{2,5}$', name):
        return "ORGANIZATION"  # Default for acronyms
    
    # Default to OTHER (can be improved with ML later)
    return "OTHER"
