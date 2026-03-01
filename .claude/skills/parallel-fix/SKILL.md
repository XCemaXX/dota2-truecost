---
name: parallel-fix
description: Apply the same fix pattern to all items using parallel agents. User shows an example fix on one item, then this skill applies it to all items in parallel batches.
user-invocable: true
argument-hint: [description of the fix to apply]
---

# Parallel Item Fix

Apply the fix pattern described in **$ARGUMENTS** to all items in parallel.

## Item Batches

**Batch 1:** item_branches, item_gauntlets, item_slippers, item_mantle, item_circlet, item_ring_of_protection, item_ring_of_regen, item_sobi_mask, item_wind_lace, item_fluffy_hat

**Batch 2:** item_blight_stone, item_blades_of_attack, item_belt_of_strength, item_boots_of_elves, item_robe, item_crown, item_gloves, item_boots, item_chainmail, item_ring_of_health

**Batch 3:** item_void_stone, item_cloak, item_energy_booster, item_lifesteal, item_gem, item_helm_of_iron_will, item_broadsword, item_diadem, item_ogre_axe, item_blade_of_alacrity

**Batch 4:** item_staff_of_wizardry, item_blitz_knuckles, item_vitality_booster, item_falcon_blade, item_point_booster, item_cornucopia, item_talisman_of_evasion, item_claymore, item_platemail, item_pers

**Batch 5:** item_ghost, item_mithril_hammer, item_oblivion_staff, item_ring_of_tarrasque, item_tiara_of_selemene, item_hyperstone, item_kaya, item_sange, item_yasha, item_demon_edge

**Batch 6:** item_blink, item_ultimate_orb, item_eagle, item_reaver, item_mystic_staff, item_soul_booster, item_relic, item_dagon, item_dagon_2, item_dagon_3, item_dagon_4, item_dagon_5

**Batch 7:** item_heart, item_greater_crit, item_rapier, item_faerie_fire, item_enchanted_mango

**Batch 8:** item_magic_stick, item_infused_raindrop, item_orb_of_frost, item_orb_of_venom, item_buckler, item_ring_of_basilius, item_headdress, item_magic_wand, item_bracer, item_wraith_band

**Batch 9:** item_null_talisman, item_voodoo_mask, item_soul_ring, item_javelin, item_shadow_amulet, item_power_treads, item_pavise, item_ancient_janggo, item_vanguard, item_mekansm

**Batch 10:** item_dragon_lance, item_lesser_crit, item_hand_of_midas, item_vladmir, item_force_staff, item_rod_of_atos, item_aether_lens, item_travel_boots

**Batch 11:** item_armlet, item_cyclone, item_heavens_halberd, item_echo_sabre, item_basher, item_invis_sword, item_orchid, item_revenants_brooch

**Batch 12:** item_pipe, item_lotus_orb, item_bfury, item_moon_shard, item_black_king_bar, item_sange_and_yasha, item_kaya_and_sange, item_yasha_and_kaya, item_travel_boots_2, item_gungir

**Batch 13:** item_manta, item_monkey_king_bar, item_sphere, item_octarine_core, item_refresher, item_assault, item_shivas_guard, item_sheepstick

**Batch 14:** item_butterfly, item_skadi, item_devastator, item_blood_grenade, item_bottle, item_urn_of_shadows, item_tranquil_boots, item_orb_of_corrosion, item_arcane_boots

**Batch 15:** item_phase_boots, item_veil_of_discord, item_mask_of_madness, item_glimmer_cape, item_holy_locket, item_blade_mail, item_diffusal_blade, item_helm_of_the_dominator, item_solar_crest, item_phylactery

**Batch 16:** item_spirit_vessel, item_witch_blade, item_mage_slayer, item_meteor_hammer, item_maelstrom, item_aeon_disk, item_desolator, item_eternal_shroud, item_crimson_guard, item_boots_of_bearing

**Batch 17:** item_guardian_greaves, item_bloodstone, item_nullifier, item_hurricane_pike, item_radiance, item_harpoon, item_satanic, item_ethereal_blade, item_mjollnir, item_helm_of_the_overlord

**Batch 18:** item_silver_edge, item_disperser, item_abyssal_blade, item_bloodthorn, item_overwhelming_blink, item_swift_blink, item_arcane_blink, item_wind_waker

## Workflow

1. Confirm the fix pattern with the user (show example from their demonstration)
2. Launch parallel agents — one per batch (up to 6 concurrent)
3. Each agent:
   - Reads `src/axioms/axiom_rules.yaml` and `output/effective_costs.json`
   - For each item in its batch, applies the fix pattern
   - Reports changes made and items skipped (with reason)
4. Collect results from all agents
5. Run full pipeline: `cd src && source venv/bin/activate && python -m pipeline.02_resolve_axioms && python -m pipeline.03_calculate_costs && python -m pipeline.04_generate_output`
6. Run tests: `python -m pytest tests/ -v`
7. Present summary table of all changes

**Rules:**
- Do NOT modify items that don't match the fix pattern
- Preserve existing overrides — only add/change what's needed
- Report any items where the fix is ambiguous
