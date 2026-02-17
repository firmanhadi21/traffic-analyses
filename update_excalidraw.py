import json
import copy

def update_excalidraw():
    file_path = '/Users/macbook/Dropbox/GitHub/traffic-analyses/figures/pipeline_architecture.excalidraw'
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    elements = data['elements']
    
    # Check if EDA already exists to prevent double-add
    for el in elements:
        if el.get('id') == 'eda-box':
            print("EDA box already exists.")
            return

    # Helper to find an element by ID
    def get_el(eid):
        for el in elements:
            if el.get('id') == eid:
                return el
        return None

    # IDs to shift down by 100px
    ids_to_shift = {
        'stage3-box', 'stage3-title', 'stage3-detail',
        'stage4-box', 'stage4-title', 'stage4-detail',
        'stage5-box', 'stage5-title', 'stage5-detail',
        'arrow4', 'arrow5', 'arrow6' # arrow6 is the output arrow from stage 4? check Excalidraw file 
        # arrow6 connects stage 4 to output? No, arrow 6 is synthesis output?
        # Let's re-read arrow6: x=600, y=330. Stage 3 is y=280. So arrow6 is likely from stage 3.
        # If stage 3 moves to 380, arrow6 must move to 430.
    }
    
    # arrow6 connects x=600, y=330.
    # Stage 3 box is y=280, height 80. Center y ~ 320.
    # So arrow6 is associated with Stage 3.
    
    # Mapping for text updates
    text_updates = {
        'stage3-title': 'Stage 4: Geostatistics',
        'stage4-title': 'Stage 5: Network',
        'stage5-title': 'Stage 6: Synthesis'
    }

    n_elements = []
    
    for el in elements:
        eid = el.get('id')
        new_el = copy.deepcopy(el)
        
        if eid in ids_to_shift:
            new_el['y'] += 100
        
        if eid == 'arrow6':
             # arrow6 is special case, check if it needs shift
             # y=330. It's close to Stage 3 (y=280..360).
             # If Stage 3 becomes Stage 4 (y=380..460), arrow6 should be at y=430.
             new_el['y'] += 100

        if eid in text_updates:
            new_el['text'] = text_updates[eid]
            
        n_elements.append(new_el)
    
    # Base for new EDA elements (Clone Stage 2)
    # Stage 2 is at y=180. We want EDA at y=280.
    s2_box = get_el('stage2-box')
    s2_title = get_el('stage2-title')
    s2_detail = get_el('stage2-detail')
    arrow2 = get_el('arrow2') # connects 1->2 (y=160).
    arrow3 = get_el('arrow3') # connects 2->3 (y=260).
    
    # Create EDA box at y=280
    eda_box = copy.deepcopy(s2_box)
    eda_box['id'] = 'eda-box'
    eda_box['y'] = 280
    
    eda_title = copy.deepcopy(s2_title)
    eda_title['id'] = 'eda-title'
    eda_title['y'] = 290
    eda_title['text'] = 'Stage 3: EDA'
    
    eda_detail = copy.deepcopy(s2_detail)
    eda_detail['id'] = 'eda-detail'
    eda_detail['y'] = 315
    eda_detail['text'] = 'Matplotlib/Seaborn\nQC & Validation'
    
    # Create arrow from EDA to Stage 4 (old Stage 3)
    # arrow3 was at 260. New arrow needs to be at 360 (connecting 280 box to 380 box).
    eda_arrow = copy.deepcopy(arrow3)
    eda_arrow['id'] = 'arrow-eda'
    eda_arrow['y'] = 360 
    
    n_elements.extend([eda_box, eda_title, eda_detail, eda_arrow])
    
    data['elements'] = n_elements
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    print("Updated Excalidraw file.")

if __name__ == '__main__':
    update_excalidraw()
