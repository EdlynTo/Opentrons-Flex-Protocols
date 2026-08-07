from opentrons import protocol_api
import math
import urllib.request
import json
from opentrons import types

metadata = {
    "protocolName": "Ceres plasma protocol for 5ul plasma - Beads separate",
    "author": "Calvin",
    "description": "Ceres protocol 5ul plasma. Large plate, 3 BeadTubes api2.27",
    }

requirements = {"robotType": "Flex", "apiLevel": "2.27"}
#lid needs to be setup differently in API 2.27
#meniscus tracking works for full tubes

def add_parameters(parameters):
# ======================== RUNTIME PARAMETERS ========================
    parameters.add_int(
        variable_name="COLUMNS",
        display_name="Number of Columns (Samples)",
        description="Number of samples divided by 8 rounded up",
        default=12, minimum=3, maximum=12,
    )

    parameters.add_int(
        variable_name="incubation_time",
        display_name="Incubation Time",
        choices=[
            {"display_name": "2 hrs", "value": 2},
            {"display_name": "1 hrs", "value": 1},
        ],
        description="1 or 2 hours digestion",
        default=2,
    )

    # parameters.add_bool(
    #     variable_name="dry_run",
    #     display_name="Dry Run",
    #     description="Skip incubation delays and return tips.",
    #     default=False,
    # )

    parameters.add_int(
        display_name="Run Type",
        variable_name="run_type",
        default=1,
        choices=[
            {'display_name':'Sample Run','value':1},
            {'display_name':'Water Run','value':2},
            {'display_name':'Dry Run','value':3}
        ],
        description="What type of run is this going to be?"
    )

# ======================== IMPORT PARAMETERS ======================== 
def run(protocol):
    run_type = protocol.params.run_type
    sample_run = True if run_type == 1 else False
    water_run = True if run_type == 2 else False
    dry_run = True if run_type == 3 else False
    COLUMNS = protocol.params.COLUMNS
    digest_time = protocol.params.incubation_time
    
# ======================== DECK SETUP ========================   
    tips200 = [
            protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "A3"),
            protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "B3"),
            protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "C3"),
    ] #can add more tips to other locations
    left_pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=tips200)
    right_pipette = protocol.load_instrument("flex_8channel_1000", "right", tip_racks=tips200)
    
    # Modules
    mag = protocol.load_module(module_name="magneticBlockV1", location="C1")
    hs_mod = protocol.load_module(
        module_name="heaterShakerModuleV1", location="D1")
    hs_mod.open_labware_latch()
    chute = protocol.load_waste_chute()
    
    # Labware
    sample_plate = protocol.load_labware(
        "thermofisher_96_wellplate_250ul", "A1", "sample plate - large"
    )    
    multiplex_reservoir = protocol.load_labware("nest_96_wellplate_2ml_deep", location="B2")
    #reagent_plate = protocol.load_labware("thermofisher_96_wellplate_250ul", "A2", "reagent plate - large")
    #lid = protocol.load_labware("opentrons_tough_pcr_auto_sealing_lid", location="C2") #lid is different in new API
    tube_rack = protocol.load_labware("opentrons_24_tuberack_eppendorf_2ml_safelock_snapcap", "C2", "tube rack")
    final_plate = protocol.load_labware("opentrons_96_wellplate_200ul_pcr_full_skirt", "B1", "reagent plate")    
    working_reagent_reservoir = protocol.load_labware("nest_12_reservoir_15ml", "D2")
    #falcon_tube_rack = protocol.load_labware("opentrons_10_tuberack_falcon_4x50ml_6x15ml_conical", "C2", "falcon rack")
    
# ======================== RUNTIME PARAMETERS ========================       
    # defining variables
    wash_volume = 100  #µl water
    shake_speed = 1400  #rpm
    num_washes = 2
    bead_settle_time = 60  # seconds
    dtt_conc = 500 #mM
    iaa_conc = 375 #mM
    incubation_temp = 47 #C

    bead_vol = 20  # µl total beads
    trypsin_vol = 10
    digest_buffer_vol = 100

    #Loaded volumes
    bead_amt = (7 * 8 * COLUMNS + 50)  # ul
    binding_buffer_amt = (15 * 8 * COLUMNS + 60)  # ul
    dtt_iaa_amt = (5 * 8 * COLUMNS + 100) # ul
    wash_buffer_amt = (200 * 8 * COLUMNS + 1000) # ul
    trypsin_amt = (10 * 8 * COLUMNS +60) #ul
    digest_buffer_amt = (200 * 8 * COLUMNS + 1000)  # ul
    formic_acid_amt = (10 * 8 * COLUMNS + 1000)  # ul   
    
    amt_of_sample_to_collect = 100
    amt_final_buffer_to_add = 5
    amt_extra_in_2ml_reservoir = 10


# ======================== REAGENT INFO ========================   
    bind_buffer_tube = tube_rack['A1']
    bead_tubeA = tube_rack["A2"]
    bead_tubeB = tube_rack["A3"]
    bead_tubeC = tube_rack["A4"]
    dtt_tube = tube_rack["B1"]
    iaa_tube = tube_rack["B2"]
    trypsin_tube = tube_rack["B3"]
    #Tube rack has 6 columns x 4 rows
    
    wash_buffer_storage = [
        working_reagent_reservoir["A1"],
        working_reagent_reservoir["A2"],
        working_reagent_reservoir["A3"],
        ]
    digest_buffer_storage = [
        working_reagent_reservoir["A4"],
        working_reagent_reservoir["A5"],
        working_reagent_reservoir["A6"],
        ]
    formic_acid_storage = working_reagent_reservoir["A7"]

    trash_storage1 = working_reagent_reservoir["A11"]
    trash_storage2 = working_reagent_reservoir["A12"]

    
    # Defining liquids
    sample_liq = protocol.define_liquid("sample", "", "#ff2503")
    bead_liq = protocol.define_liquid("Bead Mix", "Ceres bead ABC", "#000000")
    bind_buffer_liq = protocol.define_liquid("Binding Buffer", "Ceres Buffer 4", "#8d32a8")
    dtt_liq = protocol.define_liquid("DTT Stock", "DTT Stock", "#ff8503")
    iaa_liq = protocol.define_liquid("IAA Stock", "IAA Stock", "#df02f7")
    digestion_buffer_liq = protocol.define_liquid("Digestion Buffer", "ABC", "#fafa02")
    trypsin_liq = protocol.define_liquid("Trypsin", "Trypsin", "#fafa02")
    wash_buffer_liq = protocol.define_liquid("Wash Buffer", "Water", "#05a1f5")
    formic_acid_liq = protocol.define_liquid("Formic Acid", "5% Formic acid", "#42f5c2") 
    
    # Loading Liquids in locations
    bead_tubeA.load_liquid(bead_liq, bead_amt)
    bead_tubeB.load_liquid(bead_liq, bead_amt)
    bead_tubeC.load_liquid(bead_liq, bead_amt)
    bind_buffer_tube.load_liquid(bind_buffer_liq, binding_buffer_amt)    
    dtt_tube.load_liquid(dtt_liq, dtt_iaa_amt)
    iaa_tube.load_liquid(iaa_liq, dtt_iaa_amt)
    trypsin_tube.load_liquid(trypsin_liq, trypsin_amt)

    formic_acid_storage.load_liquid(formic_acid_liq, formic_acid_amt)

    for i in range (0, COLUMNS*8):
        sample_plate.wells()[i].load_liquid(sample_liq, 20)

    #load wash buffer
    start = 1
    wbReservoirs = ["A1", "A2", "A3"]
    for i in range(0, math.ceil(wash_buffer_amt /1000 / 10)):
        if i == math.ceil(wash_buffer_amt /1000 / 10) - 1:  # on last iteration
            wb_to_transfer = 10500
        else:
            wb_to_transfer = 10500
        working_reagent_reservoir[wbReservoirs[i]].load_liquid(
            wash_buffer_liq, wb_to_transfer
        )
        start += 1
    # load digestion buffer
    start = 4
    dbReservoirs = ["A4", "A5", "A6"]
    for i in range(0, math.ceil(digest_buffer_amt /1000 / 10)):
        if i == math.ceil(digest_buffer_amt /1000 / 10) - 1:  # on last iteration
            db_to_transfer = 10500
        else:
            db_to_transfer = 10500
        working_reagent_reservoir[dbReservoirs[i]].load_liquid(
            digestion_buffer_liq, db_to_transfer
        )
        start += 1

# ======================== STAGE ========================  
    staging_slots = ["A2", "A4", "B4", "C4", "D4"]
    staging_racks = [
        protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", slot)
        for slot in staging_slots
    ]
    pipette_max = 1000 - 5
    

    # REPLENISHING TIPS
    count = 0

# ======================== FUNCTIONS ======================== 
    def pick_up(pipette):
        nonlocal tips200
        nonlocal staging_racks
        nonlocal count

        try:
            pipette.tip_racks = tips200
            pipette.pick_up_tip()

        except protocol_api.labware.OutOfTipsError:
            print("\nout of tips\n")
            check_tips()
            pick_up(pipette)

    def check_tips():
        nonlocal tips200
        nonlocal staging_racks
        nonlocal count
        tip_box_slots = ["A3", "B3"]
        for i in range(0, len(tip_box_slots)):
            bottom_right_well = tips200[i].wells_by_name()["H12"]
            top_right_well = tips200[i].wells_by_name()["A12"]
            if (bottom_right_well.has_tip and top_right_well.has_tip) or protocol.deck[
                "D4"
            ] == None:
                protocol.comment(
                    "A tip is present in the bottom-right corner (H12). or all staging slots are empty"
                )
                if protocol.deck["D4"] == None:
                    protocol.comment("No tip box detected in slot D4.")
                    staging_slots = ["A2", "A4", "B4", "C4", "D4"]
                    staging_racks = [
                        protocol.load_labware(
                            "opentrons_flex_96_filtertiprack_200uL", slot
                        )
                        for slot in staging_slots
                    ]
                continue
            else:
                print("starting moving phase")
                protocol.move_labware(
                    labware=tips200[i], new_location=chute, use_gripper=True if sample_run else False
                )
                rack_num = 0
                for slot in ["A2", "A4", "B4", "C4", "D4"]:
                    labware = protocol.deck[slot]
                    if labware and labware.is_tiprack:
                        tips200[i] = staging_racks[rack_num]
                        protocol.move_labware(
                            labware=staging_racks[rack_num],
                            new_location=tip_box_slots[i],
                            use_gripper=True,
                        )
                        break
                    else:
                        protocol.comment(f"No tip box detected in slot {slot}.")
                        rack_num += 1
                        pass
    
    def remove_tip(pipette):
        if dry_run or water_run:
            pipette.return_tip()
        else:
            pipette.drop_tip(chute)

    def remove_tip_dispense_trash(pipette, amt):
        if dry_run or water_run:
            pipette.dispense(amt, trash_storage1.bottom(0))
            pipette.return_tip()
        else:
            pipette.dispense(amt, trash_storage1.bottom(0))
            pipette.drop_tip(chute)

    def aspirate_supernatent_to_trash1(pipette, amt, speed=0.05, discard_tip=True, height=0.5):
        for i in range(0, COLUMNS):
            if pipette.has_tip == False:
                pick_up(pipette)
            pipette.aspirate(
                amt, sample_plate["A" + str(i + 1)].bottom(height), rate=speed
            )
            pipette.dispense(amt, trash_storage1.bottom(5))
            pipette.blow_out( trash_storage1.top(0))
            if discard_tip:
                remove_tip(pipette)    
            if pipette.has_tip == True:
                remove_tip(pipette)

    def aspirate_supernatent_to_trash2(pipette, amt, speed=0.05, discard_tip=True, height=0.5):
        for i in range(0, COLUMNS):
            if pipette.has_tip == False:
                pick_up(pipette)
            pipette.aspirate(
                amt, sample_plate["A" + str(i + 1)].bottom(height), rate=speed
            )
            pipette.dispense(amt, trash_storage2.bottom(5))
            pipette.blow_out( trash_storage2.top(0))
            if discard_tip:
                remove_tip(pipette)    
            if pipette.has_tip == True:
                remove_tip(pipette)
                
    def mix_sides(pipette, num_mixes, vol, plate, rate=0.3):
        pipette.mix(
            num_mixes, vol, plate.bottom().move(types.Point(x=0, y=1.5, z=1.5)), rate=rate
            )
        pipette.mix(
            num_mixes,
            vol,
            plate.bottom().move(types.Point(x=0, y=-1.5, z=1.5)),
            rate=rate,
            )
        pipette.mix(
            num_mixes, vol, plate.bottom().move(types.Point(x=1.5, y=0, z=1.5)), rate=rate
            )
        pipette.mix(
            num_mixes,
            vol,
            plate.bottom().move(types.Point(x=-1.5, y=0, z=1.5)),
            rate=rate,
            )
        pipette.mix(1, vol, plate.bottom(1), rate=0.1)
    
    
    def fancy_mix_sides(pipette, num_mixes, vol, plate, rate=0.3, num_points = 4):
        radius = 3.2  # mm
        # num_points = 8  # change to 12 or more for finer circle
        z_offset = 1.5  # mm, height above the bottom of the well
    
        for i in range(num_points):
            angle_rad = 2 * math.pi * i / num_points
            x = radius * math.cos(angle_rad)
            y = radius * math.sin(angle_rad)
            for a in range (0, num_mixes):
                pipette.aspirate(vol, plate.bottom(1), rate=rate)
                pipette.dispense(vol, plate.bottom().move(types.Point(x=x, y=y, z=z_offset)), rate=rate)

        # Final central mix
        pipette.mix(1, vol, plate.bottom(z=z_offset), rate=0.1)

    def delay(seconds, msg=""):
        if dry_run:
            return
        check_tips()
        protocol.delay(seconds=seconds, msg=msg)

    
    pipette_max = 200 - 5

    def heat_shake(temp=None, time=None, rpm=None):
        if temp:
            hs_mod.set_and_wait_for_temperature(temp)
        if rpm:
            hs_mod.set_and_wait_for_shake_speed(rpm)
        if time:
            protocol.delay(seconds=time)
        if temp:
            hs_mod.deactivate_heater()
        if rpm:
            hs_mod.deactivate_shaker()   



# --------------PROTOCOL STARTS HERE----------------
    protocol.comment('\n---Beginning Protocol---\n')
    protocol.comment('\nStarting Enrichment\n')
    protocol.comment('\nAliquot Buffer4\n')
    hs_mod.open_labware_latch()
    pick_up(left_pipette)
    for i in range(0, 8):
        b4_in_well = (
            15 * COLUMNS + amt_extra_in_2ml_reservoir
            ) #Vol Buffer 4 transfered to well
        left_pipette.aspirate(b4_in_well, bind_buffer_tube.bottom(0), 1)
        left_pipette.dispense(b4_in_well, multiplex_reservoir.wells()[i].top(-20), 1) #column1 #depth 38mm
        left_pipette.blow_out(multiplex_reservoir.wells()[i].top(-20))
    remove_tip(left_pipette)
    
    protocol.comment('\nTransfer Buffer4 to Plate\n')        
    pick_up(right_pipette) #try to dispense without contamination
    for i in range(0, COLUMNS):
        right_pipette.aspirate(15, multiplex_reservoir["A1"].bottom(0.1), 0.2)
        right_pipette.dispense(15, sample_plate["A" + str(i + 1)].top(-5), 0.5)
        right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
    remove_tip(right_pipette)

    #protocol.pause("Prepare Bead Mix and Place in position A2 of TubeRack C2")
    protocol.comment('\nAliquot Bead A\n')
    pick_up(left_pipette)
    bead_in_well = (
                7 * COLUMNS + amt_extra_in_2ml_reservoir
                ) #Vol Beads transfered to well
    
    #left_pipette.measure_liquid_height(bead_tube) #meniscus tracking
    #for i in range(0, 8):
    #    left_pipette.aspirate(bead_in_well, 
    #                          bead_tube.bottom(1) if not COLUMNS>8 else bead_tube.meniscus(-3), 1) ###tube depth 39mm
    #    left_pipette.dispense(bead_in_well, multiplex_reservoir.wells()[i + 8].top(-20), 1) #column2
    #    left_pipette.blow_out(multiplex_reservoir.wells()[i+8].top(-20))
    
    #mix beads
    mix_vol = bead_amt/4 #volume to be mixed
    left_pipette.mix(repetitions=3, volume=mix_vol, location=bead_tubeA.bottom(0.5))
    
    for i in range(0, 8):
        left_pipette.aspirate(bead_in_well, 
                              bead_tubeA.bottom(1), 0.3) ###tube depth 39mm
        left_pipette.dispense(bead_in_well, multiplex_reservoir.wells()[i + 8].top(-20), 1) #column2    
        left_pipette.blow_out(multiplex_reservoir.wells()[i + 8].top(-20))
    remove_tip(left_pipette)
    protocol.comment('\nAliquot Bead B\n')     
    pick_up(left_pipette)
    left_pipette.mix(repetitions=3, volume=mix_vol, location=bead_tubeB.bottom(0.5))
    left_pipette.aspirate(mix_vol, bead_tubeA.bottom(0.4), 1)
    left_pipette.dispense(mix_vol, bead_tubeA.bottom(2), 1)
    for i in range(0, 8):
        left_pipette.aspirate(bead_in_well, 
                              bead_tubeB.bottom(1), 0.3) ###tube depth 39mm
        left_pipette.dispense(bead_in_well, multiplex_reservoir.wells()[i + 16].top(-20), 1) #column3    
        left_pipette.blow_out(multiplex_reservoir.wells()[i + 16].top(-20))
    remove_tip(left_pipette)
    protocol.comment('\nAliquot Bead C\n') 
    pick_up(left_pipette)
    left_pipette.mix(repetitions=3, volume=mix_vol, location=bead_tubeC.bottom(0.5))
    for i in range(0, 8):
        left_pipette.aspirate(bead_in_well, 
                              bead_tubeC.bottom(1), 0.3) ###tube depth 39mm
        left_pipette.dispense(bead_in_well, multiplex_reservoir.wells()[i + 24].top(-20), 1) #column4    
        left_pipette.blow_out(multiplex_reservoir.wells()[i + 24].top(-20))
    remove_tip(left_pipette)
    
    protocol.comment('\nTransfer Bead A to Plate\n')        
    pick_up(right_pipette) #try dispense without contamination
    for i in range(0, COLUMNS):
        right_pipette.aspirate(7, multiplex_reservoir["A2"].bottom(0.1), 0.2)
        right_pipette.dispense(7, sample_plate["A" + str(i + 1)].top(-5), 0.5)
        right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
    protocol.comment('\nTransfer Bead B to Plate\n')        
    for i in range(0, COLUMNS):
        right_pipette.aspirate(7, multiplex_reservoir["A3"].bottom(0.1), 0.2)
        right_pipette.dispense(7, sample_plate["A" + str(i + 1)].top(-5), 0.5)
        right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
    protocol.comment('\nTransfer Bead C to Plate\n')        
    for i in range(0, COLUMNS):
        right_pipette.aspirate(7, multiplex_reservoir["A4"].bottom(0.1), 0.2)
        right_pipette.dispense(7, sample_plate["A" + str(i + 1)].top(-5), 0.5)
        right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
    remove_tip(right_pipette)


# --------------Bead Incubation----------------
    protocol.move_labware(sample_plate, hs_mod, use_gripper=True)
    protocol.comment('1000 rpm shake for 30 min\n')
    hs_mod.close_labware_latch()
    heat_shake(rpm=1000, time=1800 if not dry_run else 5)
    hs_mod.open_labware_latch()
    protocol.move_labware(sample_plate, mag, use_gripper=True)
    protocol.delay(seconds=60 if not dry_run else 5, msg='Delaying for 1 minute for beads to pellet')
    
    aspirate_supernatent_to_trash1(right_pipette, 40, discard_tip=False) #Total volume of beads+bb+sample
 
# --------------Bead Wash----------------
    protocol.comment('Wash beads with 150ul water\n')
    protocol.move_labware(sample_plate, hs_mod, use_gripper=True)
    hs_mod.close_labware_latch()
    pick_up(right_pipette)
    for i in range(0, COLUMNS):
        wash_buffer_amt -= wash_volume * 8
        right_pipette.aspirate(
                wash_volume,
                wash_buffer_storage[math.ceil(wash_buffer_amt / 10500) - 1].bottom(2),
                0.4,
            )
        right_pipette.dispense(
                wash_volume,
                sample_plate["A" + str(i + 1)].top(-4),
                rate=0.5,
            )
    remove_tip(right_pipette)

    protocol.comment("Gentle agitation for 1 minute (" + str(shake_speed) + "rpm)")
    heat_shake(time=60, rpm=1000)
    hs_mod.deactivate_shaker()
    hs_mod.open_labware_latch()
    protocol.move_labware(sample_plate, mag, use_gripper=True)
    protocol.delay(seconds=60 if not dry_run else 5, msg='Delaying for 1 minute for beads to pellet')
    hs_mod.close_labware_latch()
    aspirate_supernatent_to_trash1(right_pipette, wash_volume, discard_tip=False)
    hs_mod.open_labware_latch()
    protocol.move_labware(sample_plate, hs_mod, use_gripper=True)
    hs_mod.close_labware_latch()    

    pick_up(right_pipette)
    for i in range(0, COLUMNS):
        right_pipette.aspirate(100, working_reagent_reservoir["A4"], 0.1)  #digest buffer 1
        right_pipette.dispense(100, sample_plate["A" + str(i + 1)].top(-5), 0.5)
    remove_tip(right_pipette)
    check_tips()
    

# --------------Reduction Alkylation----------------
    protocol.comment('\nAliquot DTT\n')
    hs_mod.set_target_temperature(37)
    pick_up(left_pipette)
    dtt_iaa_aliquot = 5 * COLUMNS + COLUMNS * 2
    for i in range(0, 8):
        left_pipette.aspirate(dtt_iaa_aliquot, dtt_tube.bottom(0), 1)
        left_pipette.dispense(dtt_iaa_aliquot, multiplex_reservoir.wells()[i + 32].top(-20), 1) #column5  
        left_pipette.blow_out(multiplex_reservoir.wells()[i + 32].top(-20))
    remove_tip(left_pipette)
    protocol.comment('\nTransfer DTT to Plate\n')        
    pick_up(right_pipette)
    for i in range(0, COLUMNS):
        right_pipette.aspirate(7, multiplex_reservoir["A3"].bottom(0.1), 0.2)
        right_pipette.dispense(7, sample_plate["A" + str(i + 1)].top(-4), 0.5)
        right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
    remove_tip(right_pipette)  
    
    heat_shake(temp=37, time=1800 if not dry_run else 5, rpm=400) #30 minutes at 37
    delay(seconds=300 if not dry_run else 5, msg="Waiting 5 minutes for heat shaker to cool down")

    protocol.comment('\nAliquot IAAC\n')
    pick_up(left_pipette)
    for i in range(0, 8):
        left_pipette.aspirate(dtt_iaa_aliquot, iaa_tube.bottom(0), 1)
        left_pipette.dispense(dtt_iaa_aliquot, multiplex_reservoir.wells()[i + 40].top(-20), 1) #column6  
        left_pipette.blow_out(multiplex_reservoir.wells()[i + 40].top(-20))
    remove_tip(left_pipette)
   
    protocol.comment('\nTransfer IAA to Plate\n')        
    pick_up(right_pipette)
    for i in range(0, COLUMNS):    
        right_pipette.aspirate(7, multiplex_reservoir["A4"].bottom(0.1), 0.2)
        right_pipette.dispense(7, sample_plate["A" + str(i + 1)].top(-5), 0.5)
        right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
    remove_tip(right_pipette)  
    heat_shake(time=1800 if not dry_run else 5, rpm=1000) #30 minutes at rt

    hs_mod.open_labware_latch()
    protocol.move_labware(sample_plate, mag, use_gripper=True)
    protocol.delay(seconds=60 if not dry_run else 5, msg='Delaying for 1 minute for beads to pellet')
    
    aspirate_supernatent_to_trash2(right_pipette, 110, discard_tip=False) #Total volume of wash
    protocol.move_labware(sample_plate, hs_mod, use_gripper=True)
    hs_mod.close_labware_latch()    
    pick_up(right_pipette)
    for i in range(0, COLUMNS):
        right_pipette.aspirate(100, working_reagent_reservoir["A5"], 0.1) #digest buffer 2
        right_pipette.dispense(100, sample_plate["A" + str(i + 1)].top(-5), 0.5)
    remove_tip(right_pipette)
    check_tips()


# --------------Digestion----------------
    protocol.comment('\nAliquot Trypsin\n')
    hs_mod.set_target_temperature(47)
    pick_up(left_pipette)
    trypsin_aliquot = 10 * COLUMNS + COLUMNS*2
    for i in range(0, 8):
        left_pipette.aspirate(trypsin_aliquot, trypsin_tube.bottom(0), 1)
        left_pipette.dispense(trypsin_aliquot, multiplex_reservoir.wells()[i + 48].top(-20), 1) #column7
        left_pipette.blow_out(multiplex_reservoir.wells()[i+48].top(-20))
    remove_tip(left_pipette)
    
    protocol.comment('\nTransfer Trypsin to Plate\n')        
    pick_up(right_pipette)
    for i in range(0, COLUMNS):
        right_pipette.aspirate(10, multiplex_reservoir["A5"].bottom(0.1), 0.2)
        right_pipette.dispense(10, sample_plate["A" + str(i + 1)].top(-5), 0.5)
        right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
    remove_tip(right_pipette)  

    #hs_mod.open_labware_latch()
    #protocol.move_labware(labware=lid, new_location=sample_plate, use_gripper=True)
    #hs_mod.close_labware_latch()
    heat_shake(temp=47, time= digest_time*60*60 if not dry_run else 5, rpm=1000) #2 hours at 47
    hs_mod.open_labware_latch()
    #protocol.move_labware(labware=lid, new_location="C3", use_gripper=True)
    protocol.move_labware(sample_plate, mag, use_gripper=True)
    protocol.delay(seconds=60 if not dry_run else 5, msg='Delaying for 1 minute for beads to pellet')        
    
    protocol.comment('\nTransfer Peptides to New Plate\n') 
    for i in range(0, COLUMNS):
        pick_up(right_pipette)
        right_pipette.aspirate(100, sample_plate["A" + str(i + 1)].bottom(0.1), 0.2)
        right_pipette.dispense(100, final_plate["A" + str(i + 1)].bottom(1), 0.5)
        right_pipette.blow_out(final_plate["A" + str(i + 1)].top())
        remove_tip(right_pipette)  

    protocol.comment('\nAdd Formic acid\n') 
    pick_up(right_pipette)
    for i in range(0, COLUMNS):
        right_pipette.aspirate(10, formic_acid_storage.bottom(0.1), 0.2)
        right_pipette.dispense(10, final_plate["A" + str(i + 1)].top(-5), 0.5)
        right_pipette.blow_out(final_plate["A" + str(i + 1)].top())
    remove_tip(right_pipette)  

    protocol.comment('\nProtocol Complete\n')