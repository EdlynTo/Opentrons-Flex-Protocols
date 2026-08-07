from opentrons import protocol_api
from opentrons import types
import math

metadata = {'protocolName': 'P2-iST (modified dead volumes)'}
requirements = {"robotType": "Flex","apiLevel": "2.27"}

waste_vol = 0
waste_well = 0
whichwash = 0
bead_track_vol = 0
bead_track_well = 0

def add_parameters(parameters):
    # ======================== RUNTIME PARAMETERS ========================
    parameters.add_int(
        display_name="Run Type",
        variable_name="RUN_TYPE",
        default=1,
        choices=[
            {'display_name':'Sample Run','value':1},
            {'display_name':'Water Run','value':2},
            {'display_name':'Dry Run','value':3}
        ],
        description="What type of run is this going to be?")
    parameters.add_int(
        display_name="Sample Column count",
        variable_name="COLUMNS",
        default=3,minimum=3,maximum=12,
        description="How many sample columns to process.")
    parameters.add_str(
        display_name="Multi-channel Mount",
        variable_name="MULTI_MOUNT",
        default='right',
        choices=[
            {'display_name':'Right','value':'right'},
            {'display_name':'Left','value':'left'}
        ],
        description="Which mount is the multi-channel pipette on?")
    
def run(ctx):
    # Import parameters
    RUN_TYPE = ctx.params.RUN_TYPE
    COLUMNS = ctx.params.COLUMNS
    MULTI_MOUNT = ctx.params.MULTI_MOUNT

    SINGLE_MOUNT = 'left' if MULTI_MOUNT == 'right' else 'right'

    FULL_RUN = True if RUN_TYPE == 1 else False
    
    WATER_RUN = True if RUN_TYPE == 2 else False

    DRY_RUN = True if RUN_TYPE == 3 else False

    report = False

    ### Set Up Deck ###
    # Modules
    mag = ctx.load_module('magneticBlockV1','C1')
    hs = ctx.load_module('heaterShakerModuleV1', 'D1')
    # hs_adapter = hs.load_adapter('opentrons_universal_flat_adapter') 
    hs.close_labware_latch()
    

    # Labware
    sample_plate = hs.load_labware('thermofisher_96_wellplate_250ul', label='Sample Plate (Thermo 450)')
    elution_plate = ctx.load_labware('thermofisher_96_wellplate_250ul',location='A3', label='Elution Plate (Thermo 450)')
    if COLUMNS>6:
        int_plate = elution_plate.load_labware('thermofisher_96_wellplate_250ul',label='Intermediate Plate')

    large_res = ctx.load_labware('nest_12_reservoir_15ml',location='C2',label='12 Well Res (Wash/ Waste)')

    dw_res = ctx.load_labware('nest_96_wellplate_2ml_deep',location='D2',label='Reservoir')

    tubes = ctx.load_labware('opentrons_24_tuberack_eppendorf_2ml_safelock_snapcap',location='C3',label='Tube Rack')

    chute = ctx.load_waste_chute()

    # Sample locations
    samples = sample_plate.rows()[0][:COLUMNS]
    samples_ = sample_plate.columns()[:COLUMNS]
    samples3 = elution_plate.rows()[0][:COLUMNS]
    if COLUMNS <= 6:
        samples2 = sample_plate.rows()[0][COLUMNS:2*COLUMNS]
    else:
        samples2 = int_plate.rows()[0][:COLUMNS]
    
    # Reagent Volumes
    bind_vol = 75
    bead_vol = 25
    wash_vol = 200
    lysea_vol = lyseb_vol = 20
    lyse_vol = 40
    resuspend_vol = 12.5
    digest_vol = 10
    stop_vol = 60

    # Defining Liquids
    bind_liq = ctx.define_liquid(name='P2 Bind',description=None,display_color='#ED3009')
    bead_liq = ctx.define_liquid(name='P2 Beads',description=None,display_color='#EDA509')
    wash_liq = ctx.define_liquid(name='P2 Wash',description=None,display_color='#EDE909')
    lyse_liq = ctx.define_liquid(name='Lyse A/B',description='Lyse A and Lyse B mix (1:1)',display_color='#ACED09')
    # lysea_liq = ctx.define_liquid(name='Lyse A',description=None,display_color='#ACED09')
    # lyseb_liq = ctx.define_liquid(name='Lyse B',description=None,display_color='#09ED18')
    # resuspend_liq = ctx.define_liquid(name='Resuspend',description=None,display_color='#09ED92')
    digest_liq = ctx.define_liquid(name='Digest-L/ Resuspend',description='Digest-L and Resuspend Mix',display_color='#09B8ED')
    stop_liq = ctx.define_liquid(name='Stop',description=None,display_color='#2009ED')
    samp_liq = ctx.define_liquid(name='Sample',description=None,display_color='#ED09ED')
    
    tube_liqs = [bind_liq, bead_liq, lyse_liq, stop_liq]

    # Reagent Locations (for MC and loading)
    tube_dv = 15 # dead volume needed in every tube, can probably lower this but see if it fits
    plate_dv = 3 # dead volume of 3ul per well of deep well reservoir

    def tube_load_vols(vol_per_sample, cols_per_tube):
        # Splits a reagent across as many 2mL tubes as needed, given how many
        # sample columns each tube can hold (e.g. bind = 3 cols/tube, bead = 6 cols/tube).
        # Each tube gets its own tube_dv (flat, once per tube) plus plate_dv per sample,
        # so summed across tubes this equals:
        #   vol_per_sample * total_samples + tube_dv * num_tubes + plate_dv * total_samples
        n_tubes = math.ceil(COLUMNS / cols_per_tube)
        vols = []
        cols_left = COLUMNS
        for _ in range(n_tubes):
            cols_this_tube = min(cols_per_tube, cols_left)
            samples_this_tube = cols_this_tube * 8
            vols.append(vol_per_sample*samples_this_tube + tube_dv + plate_dv*samples_this_tube)
            cols_left -= cols_this_tube
        return vols

    bind = dw_res.rows()[0][0]
    bind_ = dw_res.columns()[0]
    bind_tube = tubes.wells()[0]
    bind_tube2 = tubes.wells()[1]
    bind_tube3 = tubes.wells()[2]
    bind_tube4 = tubes.wells()[3]
    bind_tubes = [bind_tube, bind_tube2, bind_tube3, bind_tube4]
    bind_tubes = bind_tubes[:math.ceil(COLUMNS/3)]
    # 3 sample columns per bind tube
    bind_vols = tube_load_vols(bind_vol, 3)

    bead = dw_res.rows()[0][1]
    bead_ = dw_res.columns()[1]
    bead_tube = tubes.wells()[4]
    bead_tube2 = tubes.wells()[5]
    bead_tubes = [bead_tube, bead_tube2]
    bead_tubes = bead_tubes[:math.ceil(COLUMNS/6)]
    # 6 sample columns per bead tube (e.g. 2 tubes for 12 columns / 96 samples)
    bead_vols = tube_load_vols(bead_vol, 6)


    lyse = dw_res.rows()[0][2]
    lyse_ = dw_res.columns()[2]
    lyse_tube = tubes.wells()[8]
    lyse_tube2 = tubes.wells()[9]
    lyse_tube3 = tubes.wells()[10]
    lyse_tube4 = tubes.wells()[11]
    lyse_tubes = [lyse_tube, lyse_tube2, lyse_tube3, lyse_tube4]
    lyse_tubes = lyse_tubes[:math.ceil(COLUMNS/3)]
    # 3 sample columns per lyse tube
    lyse_vols = tube_load_vols(lyse_vol, 3)

    # lysea = dw_res.rows()[0][2]
    # lysea_ = dw_res.columns()[2]

    # lyseb = dw_res.rows()[0][3]
    # lyseb_ = dw_res.columns()[3]
    
    # resuspend = resuspend_ = dw_res.rows()[0][5]
    # resuspend_ = dw_res.columns()[4]

    digest = dw_res.rows()[0][3]
    digest_ = dw_res.columns()[3]
    digest_tube = tubes.wells()[6]
    # load liquid in well
    digest_tube.load_liquid(liquid=digest_liq, volume=digest_vol*8*COLUMNS+25)
    
    stop = dw_res.rows()[0][4]
    stop_ = dw_res.columns()[4]
    stop_tube = tubes.wells()[12]
    stop_tube2 = tubes.wells()[13]
    stop_tube3 = tubes.wells()[14]
    stop_tube4 = tubes.wells()[15]
    stop_tubes = [stop_tube, stop_tube2, stop_tube3, stop_tube4]
    stop_tubes = stop_tubes[:math.ceil(COLUMNS/3)]
    # 3 sample columns per stop tube
    stop_vols = tube_load_vols(stop_vol, 3)

    wash = large_res.wells()[:6]
    wash_ = large_res.wells()[:math.ceil(COLUMNS/2)]

    waste = large_res.wells()[6:]
    
    tube_vols = [bind_vols, bead_vols, lyse_vols, stop_vols]
    tube_locs = [bind_tubes, bead_tubes, lyse_tubes, stop_tubes]

    # Adding Liquids to tubes (dead volumes already included by tube_load_vols)
    for liq, vol, loc in zip(tube_liqs, tube_vols, tube_locs):
        for tube, v in zip(loc, vol):
            tube.load_liquid(liquid=liq, volume=v)


    if report:
        print(f'\nBead Tubes: {bead_tubes}\nBead Vols: {bead_vols}\n')
        print(f'\nBind Tubes: {bind_tubes}\nBind Vols: {bind_vols}\n')
        print(f'\nLyse Tubes: {lyse_tubes}\nLyse Vols: {lyse_vols}\n')
        print(f'\nStop Tubes: {stop_tubes}\nStop Vols: {stop_vols}\n')

    # Don't load liquids in DW plate --> load in tubes and set up Dw plate at start of protocol
    # for well in bind_:
    #     well.load_liquid(liquid=bind_liq,volume=bind_vol*COLUMNS+10)
    # for well in bead_:
    #     well.load_liquid(liquid=bead_liq,volume=bead_vol*COLUMNS+10)
    # for well in lyse_:
    #     well.load_liquid(liquid=lyse_liq,volume=lyse_vol*COLUMNS+10)
    # for well in stop_:
    #     well.load_liquid(liquid=stop_liq,volume=stop_vol*COLUMNS+10)
    for wells in samples_:
        for well in wells:
            well.load_liquid(liquid=samp_liq,volume=100)
    # 2 sample columns per wash well (dead volumes included by tube_load_vols)
    wash_vols = tube_load_vols(600, 2)
    for well, v in zip(wash_, wash_vols):
        well.load_liquid(liquid=wash_liq, volume=v)


    # Tips
    tips_51 = ctx.load_labware('opentrons_flex_96_tiprack_200ul',location='A1',label='50ul Tips #1 but actually its 200ul for a bit')
    tips_50 = [tips_51]
    tips_201 = ctx.load_labware('opentrons_flex_96_tiprack_200ul',location='B1',label='200ul Tips #1')
    tips_202 = ctx.load_labware('opentrons_flex_96_tiprack_200ul',location='B2',label='200ul Tips #2')
    tips_200 = [tips_201,tips_202]
    offdeck = []
    staging = []

    if COLUMNS > 3:
        tips_203 = ctx.load_labware('opentrons_flex_96_tiprack_200ul',location='B3',label='200ul Tips #3')
        tips_200.append(tips_203)
    if COLUMNS > 5:
        tips_204 = ctx.load_labware('opentrons_flex_96_tiprack_200ul',location='D4' if COLUMNS > 6 else 'A2',label='200ul Tips #4')
        if COLUMNS<=6: # add to tip list if on actual deck
            tips_200.append(tips_204)
        else:
            staging.append(tips_204) # add to staging list if in D4
    if COLUMNS > 6:
        tips_52 = ctx.load_labware('opentrons_flex_96_tiprack_50ul',location='A2',label='50ul Tips #2')
        tips_50.append(tips_52)
        tips_205 = ctx.load_labware('opentrons_flex_96_tiprack_200ul',location='A4',label='200ul Tips #5')
        staging.append(tips_205)
    if COLUMNS > 8:
        tips_206 = ctx.load_labware('opentrons_flex_96_tiprack_200ul',location='B4',label='200ul Tips #6')
        staging.append(tips_206)
    if COLUMNS > 10:
        tips_207 = ctx.load_labware('opentrons_flex_96_tiprack_200ul',location='C4',label='200ul Tips #7')
        staging.append(tips_207)
    
    # Pipettes
    single = ctx.load_instrument('flex_1channel_1000',mount=SINGLE_MOUNT)
    multi = ctx.load_instrument('flex_8channel_1000',mount=MULTI_MOUNT)

    ### Helper Functions ###
    def waste_track(vol):
        global waste_vol
        global waste_well

        waste_vol += vol
        
        if waste_vol > 1625: # 13 ml per reservoir well (1625*8 = 13000)
            waste_vol = 0
            waste_well += 1
        
        return waste_well

    def trash(labware):
        ctx.move_labware(labware,chute,use_gripper=True)

    def track_tips(pip, tips):
        pip.tip_racks=tips_50 if tips == 50 else tips_200
        new_loc = []
        try:
            pip.pick_up_tip()
        except:
            if len(staging) > 0: # if there are tips are in staging area
                new_loc.append(tips_200[0].parent)
                trash(tips_200.pop(0))
                tips_200.append(staging[0]) # move from staging list to ondeck list
                ctx.move_labware(staging.pop(0),new_loc.pop(0),use_gripper=True) # remove from staging area list and replace on deck
            else:
                length1 = len(tips_200)
                length2 = len(offdeck)
                for x in range(length1):
                    new_loc.append(tips_200[0].parent)
                    trash(tips_200.pop(0))
                for i in range(length2): # add new tips to empty locations
                    if len(new_loc) > 0:
                        tips_200.append(offdeck[0])
                        ctx.move_labware(offdeck.pop(0),new_loc.pop(0),use_gripper=False)
                    else:
                        staging.append(offdeck[0])
                        ctx.move_labware(offdeck.pop(0),'D4',use_gripper=False)
            pip.pick_up_tip()

    def remove_supernatant(pip,vol,wells,remove=False, plate=None):
        if pip == multi:
            max_vol = 200
            t = 200
        else:
            max_vol = 50
            t = 50
        ctx.comment(f'\nRemoving {vol}ul of Supernatant\n')
        for samp in wells:
            track_tips(pip, t)
            pip.aspirate(vol-10, samp.bottom(1),flow_rate=vol-10)
            ctx.delay(seconds=1)
            pip.aspirate(10, samp.bottom(0.85), flow_rate=5)
            ctx.delay(seconds=1)
            a_vol = max_vol - pip.current_volume if max_vol - pip.current_volume < 5 else 5
            if a_vol > 0:
                pip.air_gap(a_vol)
            pip.dispense(pip.current_volume, waste[waste_track(vol)].top(-2))
            ctx.delay(seconds=1)
            pip.blow_out()
            drop(pip)
            ctx.comment('\n')
        
        if remove:
            ctx.move_labware(plate, hs, use_gripper=True)
            hs.close_labware_latch()

    def bead_track(vol, skip=False):
        global bead_track_vol
        global bead_track_well

        if bead_track_vol > 1210:
            bead_track_well += 1
            bead_track_vol = 0

        if not skip:
            bead_track_vol += vol

        return bead_track_well

    def drop(pip):
        pip.drop_tip() if not DRY_RUN else pip.return_tip()

    def heat_shake(temp=None, time=None, rpm=None):
        if temp:
            hs.set_and_wait_for_temperature(temp)
        if rpm:
            hs.set_and_wait_for_shake_speed(rpm)
        if time:
            ctx.delay(seconds=time)
        if temp:
            hs.deactivate_heater()
        if rpm:
            hs.deactivate_shaker()

    def slow_withdraw(pip, w):
        pip.default_speed /= 20
        pip.move_to(well.top(-5))
        pip.default_speed *= 20

    ### Starting Protocol ###
    ctx.comment('\n---Beginning Protocol---\n')
    ctx.comment('\nTransferring Beads from Tubes to Reservoir Columns\n')
    radius = bead_tubes[0].diameter/2
    area = math.pi*(radius**2)
    # touch_off = 2 # radius minus this equals how far the tip will dispense from center of tube
    touch_off = radius
    track_tips(single, 200)
    for t, tube in enumerate(bead_tubes):
        start_height = bead_vols[t]/area
        height_=start_height + 0.5
        if report:
            ctx.comment(f'\nHeight: {height_}\n')
        range1 = COLUMNS if COLUMNS <= 6 else 6
        range2 = 0 if COLUMNS <= 6 else COLUMNS-6
        this_range = range1 if t == 0 else range2
        # extra_vol = (plate_dv/len(tube_locs))/(8*this_range) # spread this tube's plate_dv share evenly across every well/iteration draw
        extra_vol = 3 # dead volume of 3 ul per sample
        for i in range(this_range): # repeats for up to 6 columns worth of samples
            mix_r = 6 if i == 0 else 2
            for _ in range(mix_r if not DRY_RUN else 2): # mix beads before
                single.aspirate(200, tube.bottom(height_))
                single.dispense(200, tube.bottom(height_), push_out=0)
            for well in bead_:
                single.aspirate(bead_vol+extra_vol, tube.bottom(height_))
                ctx.delay(seconds=1)
                single.dispense(single.current_volume, well.bottom().move(types.Point(x=radius-touch_off,y=0,z=2)))
                ctx.delay(seconds=1)
                height_ -= (bead_vol+extra_vol)/area # update new height after each aspirate/ dispense cycle
            ctx.comment('\n')
    drop(single)

    ctx.comment('\nTransferring Bind from Tubes to Reservoir Columns\n')
    track_tips(single, 200)
    for t, tube in enumerate(bind_tubes):
        start_height = bind_vols[t]/area
        height_=start_height
        if report:
            ctx.comment(f'\nHeight: {height_}\n')
        range1 = COLUMNS if COLUMNS <= 3 else 3
        range2 = 0 if COLUMNS <= 3 else COLUMNS-3 if COLUMNS <= 6 else 3
        range3 = 0 if COLUMNS <= 6 else COLUMNS-6 if COLUMNS <= 9 else 3
        range4 = 0 if COLUMNS <= 9 else COLUMNS-9 if COLUMNS <= 6 else 3
        for i in range(range1 if t == 0 else range2 if t == 1 else range3 if t == 2 else range4): # repeats for up to 6 columns worth of samples
            for well in bind_:
                single.aspirate(bind_vol+extra_vol, tube.bottom(height_))
                ctx.delay(seconds=1)
                single.dispense(single.current_volume, well.bottom().move(types.Point(x=radius-touch_off,y=0,z=2)))
                ctx.delay(seconds=1)
                height_ -= (bind_vol+extra_vol)/area # update new height after each aspirate/ dispense cycle
            ctx.comment('\n')
    drop(single)

    ctx.comment('\nTransferring Lyse from Tubes to Reservoir Columns\n')
    track_tips(single, 200)
    for t, tube in enumerate(lyse_tubes):
        start_height = lyse_vols[t]/area
        height_=start_height
        if report:
            ctx.comment(f'\nHeight: {height_}\n')
        range1 = COLUMNS if COLUMNS <= 3 else 3
        range2 = 0 if COLUMNS <= 3 else COLUMNS-3 if COLUMNS <= 6 else 3
        range3 = 0 if COLUMNS <= 6 else COLUMNS-6 if COLUMNS <= 9 else 3
        range4 = 0 if COLUMNS <= 9 else COLUMNS-9 if COLUMNS <= 6 else 3
        for i in range(range1 if t == 0 else range2 if t == 1 else range3 if t == 2 else range4): # repeats for up to 6 columns worth of samples
            for well in lyse_:
                single.aspirate(lyse_vol+extra_vol, tube.bottom(height_))
                ctx.delay(seconds=1)
                single.dispense(single.current_volume, well.bottom().move(types.Point(x=radius-touch_off,y=0,z=2)))
                ctx.delay(seconds=1)
                height_ -= (lyse_vol+extra_vol)/area # update new height after each aspirate/ dispense cycle
            ctx.comment('\n')
    drop(single)
    
    ctx.comment('\nTransferring Stop from Tubes to Reservoir Columns\n')
    track_tips(single, 200)
    for t, tube in enumerate(stop_tubes):
        start_height = stop_vols[t]/area
        height_=start_height
        if report:
            ctx.comment(f'\nHeight: {height_}\n')
        range1 = COLUMNS if COLUMNS <= 3 else 3
        range2 = 0 if COLUMNS <= 3 else COLUMNS-3 if COLUMNS <= 6 else 3
        range3 = 0 if COLUMNS <= 6 else COLUMNS-6 if COLUMNS <= 9 else 3
        range4 = 0 if COLUMNS <= 9 else COLUMNS-9 if COLUMNS <= 6 else 3
        for i in range(range1 if t == 0 else range2 if t == 1 else range3 if t == 2 else range4): # repeats for up to 6 columns worth of samples
            for well in stop_:
                single.aspirate(stop_vol+extra_vol, tube.bottom(height_))
                ctx.delay(seconds=1)
                single.dispense(single.current_volume, well.bottom().move(types.Point(x=radius-touch_off,y=0,z=2)))
                ctx.delay(seconds=1)
                height_ -= (stop_vol+extra_vol)/area # update new height after each aspirate/ dispense cycle
            ctx.comment('\n')
    drop(single)

    ctx.comment('\nStarting Enrich\n')
    ctx.comment('\nAdding P2-Bind\n')
    track_tips(multi, 200)
    for samp in samples:
        multi.aspirate(bind_vol, bind.bottom(1), flow_rate=bind_vol)
        ctx.delay(seconds=1)
        multi.air_gap(10)
        multi.dispense(multi.current_volume, samp.top(-2))
        ctx.delay(seconds=1)
        multi.blow_out()
        ctx.comment('\n')
    drop(multi)

    ctx.comment('\nMixing and Adding Beads\n')
    for i, samp in enumerate(samples):
        track_tips(multi, 50)
        mix_vol = 45 if i < 11 else 25
        if DRY_RUN:
            mix_reps = 1
        else:
            mix_reps = 4 if i%5 == 0 else 2
        for _ in range(mix_reps):
            multi.aspirate(mix_vol, bead, flow_rate=mix_vol)
            multi.dispense(mix_vol, bead.bottom(4), push_out=0)
            ctx.delay(seconds=1)
        multi.aspirate(bead_vol, bead, flow_rate=bead_vol)
        ctx.delay(seconds=1)
        multi.air_gap(10)
        multi.dispense(multi.current_volume, samp.bottom(2),push_out=0)
        for _ in range(8 if not DRY_RUN else 1):
            multi.aspirate(50, samp, flow_rate=50)
            multi.dispense(50, samp.bottom(5),push_out=0)
        ctx.delay(seconds=1)
        multi.blow_out()
        drop(multi)
        ctx.comment('\n')

    ctx.comment('1000 rpm shake for 30 min\n')
    heat_shake(rpm=1000, time=1800 if FULL_RUN else 60 if WATER_RUN else 5)

    hs.open_labware_latch()
    ctx.move_labware(sample_plate, mag, use_gripper=True)
    ctx.delay(seconds=60 if not DRY_RUN else 5, msg='Delaying for 1 minute for beads to pellet')
    remove_supernatant(pip=multi,vol=200,wells=samples,remove=True,plate=sample_plate)

    def perform_wash(wells):
        global whichwash
        whichwash += 1
        ctx.comment(f'\nBeginning Wash #{whichwash}\n')
        if whichwash > 1:
            track_tips(multi, 200)
        else:
            if COLUMNS > 6:
                ctx.move_labware(int_plate, mag, use_gripper=True)
        for x, samp in enumerate(wells):
            src = wash[x//2]
            if whichwash == 1:
                track_tips(multi, 200)
            multi.aspirate(wash_vol, src, flow_rate=150)
            ctx.delay(seconds=1)
            multi.dispense(wash_vol, samp if whichwash == 1 else samp.top(-2), push_out=0 if whichwash == 1 else 10)
            if whichwash == 1:    
                for _ in range(3 if not DRY_RUN else 1):
                    multi.aspirate(wash_vol-20, samp, flow_rate=150)
                    multi.dispense(wash_vol-20, samp.bottom(4), push_out=0)
                    ctx.delay(seconds=1)
                multi.aspirate(wash_vol, samp,flow_rate=150)
                ctx.delay(seconds=1)
                multi.dispense(wash_vol, samples2[x])
                ctx.delay(seconds=1)
            multi.blow_out()
            if whichwash == 1:
                drop(multi)
            ctx.comment('\n')
        if whichwash > 1:
            drop(multi)
            heat_shake(rpm=1000, time=60 if not DRY_RUN else 5)
            hs.open_labware_latch()
            ctx.move_labware(int_plate if COLUMNS>6 else sample_plate, mag, use_gripper=True)
        else:
            hs.open_labware_latch()
            ctx.move_labware(sample_plate, mag if COLUMNS <= 6 else chute, use_gripper=True)
        ctx.delay(seconds=60 if not DRY_RUN else 5, msg='Waiting 1 minute for beads to pellet')
        remove_supernatant(pip=multi, wells=samples2, vol=wash_vol, remove=True if whichwash < 3 else False, plate=int_plate if COLUMNS>6 else sample_plate)

    perform_wash(samples)
    perform_wash(samples2)
    perform_wash(samples2)

    if FULL_RUN:
        hs.set_target_temperature(60)

    ctx.comment('\nBeginning Lyse\n')
    track_tips(multi, 200)
    for samp in samples2:
        multi.aspirate(lyse_vol, lyse, flow_rate=lyse_vol)
        ctx.delay(seconds=1)
        multi.air_gap(10)
        multi.dispense(multi.current_volume, samp.top(-2))
        ctx.delay(seconds=1)
        multi.blow_out()
        ctx.comment('\n')
    drop(multi)

    ctx.move_labware(sample_plate if COLUMNS<=6 else int_plate, hs, use_gripper=True)
    hs.close_labware_latch()
    heat_shake(rpm=1300, time=600 if FULL_RUN else 60 if WATER_RUN else 5)
    if FULL_RUN:
        hs.set_target_temperature(37)
    
    ctx.pause(f'Please add {digest_vol*8*COLUMNS+145}ul of Digest/ Resuspension mix to C1 of the tube rack before continuing.')

    ctx.comment('\nTransferring Resuspend/ Digest Mix to DW Res\n')
    track_tips(single, 200)
    for well in digest_:
        single.aspirate(135, digest_tube.bottom(1), flow_rate=100)
        ctx.delay(seconds=2)
        single.air_gap(10)
        single.dispense(single.current_volume, well.bottom(1))
        ctx.delay(seconds=2)
        single.blow_out()
        ctx.comment('\n')
    drop(single)


    ctx.comment('\nAdding Resuspend/ Digest Mix to Samples\n')
    track_tips(multi, 50)
    for samp in samples2:
        multi.aspirate(10, digest.top(5))
        multi.aspirate(digest_vol, digest, flow_rate=7)
        ctx.delay(seconds=1)
        multi.air_gap(5)
        multi.dispense(multi.current_volume, samp.top(-3))
        ctx.delay(seconds=1)
        multi.blow_out()
        ctx.comment('\n')
    drop(multi)

    # for samp in samples2:
    #     if not multi.has_tip:
    #         track_tips(multi)
    #     for _ in range(5 if FULL_RUN else 1):
    #         multi.aspirate(40, samp, flow_rate=30)
    #         multi.dispense(40, samp.bottom(3), push_out=0)
    #     ctx.delay(seconds=1)
    #     multi.blow_out()
    #     drop(multi)
    #     ctx.comment('\n')

    # 3/4 Addition
    heat_shake(temp=37, time=3600 if not DRY_RUN else 5) # 37C for 1 hour for digestion, shortened for testing

    ctx.comment('\nAdding Stop Solution to Samples\n')
    track_tips(multi, 200)
    for samp in samples2:
        multi.aspirate(10, stop.top(5))
        multi.aspirate(stop_vol, stop, flow_rate=stop_vol)
        ctx.delay(seconds=1)
        multi.air_gap(5)
        multi.dispense(multi.current_volume, samp.top(-3))
        ctx.delay(seconds=1)
        multi.blow_out()
        ctx.comment('\n')
    drop(multi)

    heat_shake(rpm=1300, time=60 if not DRY_RUN else 5)

    hs.open_labware_latch()
    ctx.move_labware(sample_plate if COLUMNS<=6 else int_plate, mag, use_gripper=True)
    ctx.delay(seconds=60 if not DRY_RUN else 5)

    ctx.comment('\nTransferring Supernatant to Elution Plate\n')
    for s, d in zip(samples2,samples3):
        track_tips(multi, 200)
        multi.aspirate(100, s, flow_rate=50)
        ctx.delay(seconds=1)
        multi.aspirate(15, s.bottom(0.85), flow_rate=5)
        ctx.delay(seconds=1)
        multi.dispense(multi.current_volume, d, flow_rate=100)
        ctx.delay(seconds=1)
        multi.blow_out()
        drop(multi)
        ctx.comment('\n')

    ctx.comment('\nProtocol Complete\n')