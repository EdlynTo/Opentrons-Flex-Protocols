from opentrons import protocol_api
from opentrons import types
import math

metadata = {'protocolName': 'P2-iST (Gripper Test 2)'}
requirements = {"robotType": "Flex","apiLevel": "2.24"}

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
    # hs.close_labware_latch()
    

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
    tube_dv = 25 # dead volume needed in every tube, can probably lower this but see if it fits
    plate_dv = 120 # dead volume of 15ul per well of deep well reservoir

    bind = dw_res.rows()[0][0]
    bind_ = dw_res.columns()[0]
    bind_tube = tubes.wells()[0]
    bind_tube2 = tubes.wells()[1]
    bind_tube3 = tubes.wells()[2]
    bind_tube4 = tubes.wells()[3]
    bind_tubes = [bind_tube, bind_tube2, bind_tube3, bind_tube4]
    bind_tubes = bind_tubes[:math.ceil(COLUMNS/3)]
    # bind_vol_col = bind_vol*8 # 600
    # bind_vol_tot = bind_vol_col*COLUMNS
    
    bind_vols = [
        bind_vol*8*COLUMNS if COLUMNS<=3 else bind_vol*24,
        0 if COLUMNS <= 3 else bind_vol*8*(COLUMNS-3) if COLUMNS <= 6 else bind_vol*24,
        0 if COLUMNS <= 6 else bind_vol*8*(COLUMNS-6) if COLUMNS <= 9 else bind_vol*24,
        0 if COLUMNS <= 9 else bind_vol*8*(COLUMNS-9)
    ]

    bead = dw_res.rows()[0][1]
    bead_ = dw_res.columns()[1]
    bead_tube = tubes.wells()[4]
    bead_tube2 = tubes.wells()[5]
    bead_tubes = [bead_tube, bead_tube2]
    bead_tubes = bead_tubes[:math.ceil(COLUMNS/6)]
    bead_vols = [
        bead_vol*8*COLUMNS if COLUMNS <= 6 else bead_vol*48,
        0 if COLUMNS <= 6 else bead_vol*8*(COLUMNS-6)
    ]
    # load liquid in well
    # b_vol1 = bead_vol*8*COLUMNS if COLUMNS<=6 else bead_vol*48
    # bead_tube.load_liquid(liquid=bead_liq, volume=b_vol1+tube_dv+80) # + 80 is the 10 ul extra needed per well in the DW res
    # if COLUMNS > 6:
    #     b_vol2 = bead_vol*8*(COLUMNS-6)+10
    #     bead_tube2.load_liquid(liquid=bead_liq, volume=b_vol2+tube_dv)


    lyse = dw_res.rows()[0][2]
    lyse_ = dw_res.columns()[2]
    lyse_tube = tubes.wells()[8]
    lyse_tube2 = tubes.wells()[9]
    lyse_tube3 = tubes.wells()[10]
    lyse_tube4 = tubes.wells()[11]
    lyse_tubes = [lyse_tube, lyse_tube2, lyse_tube3, lyse_tube4]
    lyse_tubes = lyse_tubes[:math.ceil(COLUMNS/3)]
    lyse_vols = [
        lyse_vol*8*COLUMNS if COLUMNS <= 3 else lyse_vol*24,
        0 if COLUMNS <= 3 else lyse_vol*8*(COLUMNS-3) if COLUMNS <= 6 else lyse_vol*24,
        0 if COLUMNS <= 6 else lyse_vol*8*(COLUMNS-6) if COLUMNS <= 9 else lyse_vol*24,
        0 if COLUMNS <= 9 else lyse_vol*8*(COLUMNS-9)
    ]

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
    digest_tube.load_liquid(liquid=digest_liq, volume=digest_vol*8*COLUMNS+plate_dv+tube_dv)
    
    stop = dw_res.rows()[0][4]
    stop_ = dw_res.columns()[4]
    stop_tube = tubes.wells()[12]
    stop_tube2 = tubes.wells()[13]
    stop_tube3 = tubes.wells()[14]
    stop_tube4 = tubes.wells()[15]
    stop_tubes = [stop_tube, stop_tube2, stop_tube3, stop_tube4]
    stop_tubes = stop_tubes[:math.ceil(COLUMNS/3)]
    stop_vols = [
        stop_vol*8*COLUMNS if COLUMNS<=3 else stop_vol*24,
        0 if COLUMNS <= 3 else stop_vol*8*(COLUMNS-3) if COLUMNS <= 6 else stop_vol*24,
        0 if COLUMNS <= 6 else stop_vol*8*(COLUMNS-6) if COLUMNS <= 9 else stop_vol*24,
        0 if COLUMNS <= 9 else stop_vol*8*(COLUMNS-9)
    ]

    wash = large_res.wells()[:6]
    wash_ = large_res.wells()[:math.ceil(COLUMNS/2)]

    waste = large_res.wells()[6:]
    
    tube_vols = [bind_vols, bead_vols, lyse_vols, stop_vols]
    tube_locs = [bind_tubes, bead_tubes, lyse_tubes, stop_tubes]

    # Adding Liquids to tubes
    for x, (liq, vol, loc) in enumerate(zip(tube_liqs, tube_vols, tube_locs)):
        for tube, v in zip(loc, vol):
            tube.load_liquid(liquid=liq, volume=v+tube_dv+(plate_dv/len(tube_locs)))

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
    # for wells in samples_:
    #     for well in wells:
    #         well.load_liquid(liquid=samp_liq,volume=100)
    # wash_vols = []
    # for i in range(COLUMNS):
    #     if i%2 == 0:
    #         this_vol = 600
    #     else:
    #         this_vol = 1200
    #         wash_vols.append(this_vol)
    #     if i == COLUMNS-1:
    #         if i%2 == 0:
    #             wash_vols.append(this_vol)
    
    # for well,v in zip(wash_,wash_vols):
    #     well.load_liquid(liquid=wash_liq,volume=v*8+1500)


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

    ### Starting Protocol ###
    hs.close_labware_latch()
    ctx.comment('\n---Beginning Protocol---\n')
    hs.open_labware_latch()
    ctx.move_labware(sample_plate, mag, use_gripper=True)
    ctx.comment('\nProtocol Complete\n')