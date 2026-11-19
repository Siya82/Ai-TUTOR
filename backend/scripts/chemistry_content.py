"""
NEW 19 Nov 2026 (ADR-046): the Chemistry half of Physical Sciences.

CAPS Physical Sciences is ONE subject examined in two papers: Paper 1
Physics and Paper 2 Chemistry. THUTOra had only the physics topics. These
lists add the chemistry topics for Grades 10-12 (following the Siyavula
"Everything Science" CC BY chapters that teach them), plus the two Grade 11
physics topics that were missing (geometrical optics, 2D/3D wavefronts).

Topic tuples follow seed_dev_data.py: (name, prerequisite), where the
prerequisite is a topic name in the same grade, a (subject, grade, topic)
tuple for an earlier grade, or None. Every topic gets a `section` --
"Physics (Paper 1)" or "Chemistry (Paper 2)" -- that LEARN uses to group
the topic list. Constants: NA = 6.02 x 10^23 /mol, Vm = 22.4 dm^3/mol at STP.
"""

PHYSICS = "Physics (Paper 1)"
CHEMISTRY = "Chemistry (Paper 2)"
PS = "Physical Sciences"

CHEM_TOPICS_G10 = [
    ("Classification of Matter", None),
    ("States of Matter and the Kinetic Molecular Theory", "Classification of Matter"),
    ("The Atom", "States of Matter and the Kinetic Molecular Theory"),
    ("The Periodic Table", "The Atom"),
    ("Chemical Bonding", "The Periodic Table"),
    ("Physical and Chemical Change", "States of Matter and the Kinetic Molecular Theory"),
    ("Representing Chemical Change", "Chemical Bonding"),
    ("Reactions in Aqueous Solution", "Representing Chemical Change"),
    ("Quantitative Aspects of Chemical Change", "Representing Chemical Change"),
    ("The Hydrosphere", "Reactions in Aqueous Solution"),
]

PHYSICS_TOPICS_G11_EXTRA = [
    ("Geometrical Optics", (PS, 10, "Waves, Sound and Light")),
    ("2D and 3D Wavefronts", "Geometrical Optics"),
]

CHEM_TOPICS_G11 = [
    ("Atomic Combinations and Molecular Structure", (PS, 10, "Chemical Bonding")),
    ("Intermolecular Forces", "Atomic Combinations and Molecular Structure"),
    ("Ideal Gases", (PS, 10, "States of Matter and the Kinetic Molecular Theory")),
    ("Quantitative Aspects of Chemical Change", (PS, 10, "Quantitative Aspects of Chemical Change")),
    ("Energy and Chemical Change", (PS, 10, "Representing Chemical Change")),
    ("Acids and Bases", (PS, 10, "Reactions in Aqueous Solution")),
    ("Redox Reactions", (PS, 10, "Reactions in Aqueous Solution")),
    ("The Lithosphere", "Redox Reactions"),
]

CHEM_TOPICS_G12 = [
    ("Organic Molecules", (PS, 11, "Intermolecular Forces")),
    ("Rate and Extent of Reaction", (PS, 11, "Energy and Chemical Change")),
    ("Chemical Equilibrium", "Rate and Extent of Reaction"),
    ("Acids and Bases", (PS, 11, "Acids and Bases")),
    ("Electrochemical Reactions", (PS, 11, "Redox Reactions")),
    ("The Chemical Industry", "Chemical Equilibrium"),
]

CHEMISTRY_TOPIC_NAMES = {
    10: {n for n, _ in CHEM_TOPICS_G10},
    11: {n for n, _ in CHEM_TOPICS_G11},
    12: {n for n, _ in CHEM_TOPICS_G12},
}


def topic_section(subject_name: str, grade: int, topic_name: str) -> str | None:
    """Physical Sciences topics are Physics or Chemistry; other subjects: None."""
    if subject_name != PS:
        return None
    return CHEMISTRY if topic_name in CHEMISTRY_TOPIC_NAMES.get(grade, set()) else PHYSICS


CHEM_QUESTIONS_G10 = {
    "Classification of Matter": [
        ("Classify salt water as an element, a compound or a mixture.", "A (homogeneous) mixture"),
        ("Is copper an element, a compound or a mixture?", "An element"),
        ("Give the chemical name of NaCl.", "Sodium chloride"),
        ("What is the difference between a homogeneous and a heterogeneous mixture?",
         "A homogeneous mixture has the same composition throughout (you can't see the parts); "
         "a heterogeneous mixture is not uniform and its parts can be seen"),
    ],
    "States of Matter and the Kinetic Molecular Theory": [
        ("What happens to the average kinetic energy of the particles when a substance is heated?", "It increases"),
        ("Name the phase change from a solid directly to a gas.", "Sublimation"),
        ("Water boils at 100 degrees Celsius at sea level. What is this temperature in kelvin?", "373 K"),
        ("In which phase are the forces between particles strongest: solid, liquid or gas?", "Solid"),
    ],
    "The Atom": [
        ("How many neutrons are in a sodium atom with mass number 23 and atomic number 11?", "12 neutrons"),
        ("What are isotopes?",
         "Atoms of the same element with the same number of protons but different numbers of neutrons"),
        ("Write the electron configuration of oxygen (Z = 8).", "1s^2 2s^2 2p^4"),
        ("Chlorine is 75% Cl-35 and 25% Cl-37. Calculate its relative atomic mass.", "35.5"),
    ],
    "The Periodic Table": [
        ("How does atomic radius change across a period from left to right?", "It decreases"),
        ("Elements in the same group have the same number of ...", "valence electrons"),
        ("Define first ionisation energy.",
         "The energy needed to remove the first electron from an atom in the gas phase"),
        ("In which group are the noble gases?", "Group 18"),
    ],
    "Chemical Bonding": [
        ("What type of bond forms between sodium and chlorine?", "An ionic bond"),
        ("How many lone pairs of electrons does the oxygen atom have in a water molecule?", "2"),
        ("What type of bonding holds the atoms in a piece of copper together?", "Metallic bonding"),
        ("H has electronegativity 2.1 and Cl has 3.0. Calculate the difference and name the bond type in HCl.",
         "0.9: a polar covalent bond"),
    ],
    "Physical and Chemical Change": [
        ("Is melting ice a physical or a chemical change?", "A physical change"),
        ("Is burning magnesium a physical or a chemical change?", "A chemical change"),
        ("State the law of conservation of mass.",
         "Mass is neither created nor destroyed in a chemical reaction: the total mass of the reactants "
         "equals the total mass of the products"),
        ("Is the decomposition of water by electrolysis a physical or a chemical change?", "A chemical change"),
    ],
    "Representing Chemical Change": [
        ("Balance: H2 + O2 -> H2O", "2H2 + O2 -> 2H2O"),
        ("Balance: Mg + HCl -> MgCl2 + H2", "Mg + 2HCl -> MgCl2 + H2"),
        ("Write the chemical formula for calcium hydroxide.", "Ca(OH)2"),
        ("What does (aq) mean after a formula in a chemical equation?", "Dissolved in water (aqueous)"),
    ],
    "Reactions in Aqueous Solution": [
        ("Which ions form when NaCl dissolves in water?", "Na+(aq) and Cl-(aq)"),
        ("Complete the equation: AgNO3(aq) + NaCl(aq) -> ?", "AgCl(s) + NaNO3(aq): a white precipitate of AgCl"),
        ("What is an electrolyte?", "A substance that conducts electricity when dissolved or molten, because it forms ions"),
        ("Which gas forms when an acid reacts with a carbonate?", "Carbon dioxide (CO2)"),
    ],
    "Quantitative Aspects of Chemical Change": [
        ("Calculate the molar mass of H2O (H = 1, O = 16).", "18 g/mol"),
        ("How many moles are in 36 g of water?", "2 mol"),
        ("2 mol of NaCl is dissolved to make 500 cm^3 of solution. Calculate the concentration.", "4 mol/dm^3"),
        ("How many molecules are in 0.5 mol of CO2?", "3.01 x 10^23 molecules"),
    ],
    "The Hydrosphere": [
        ("Name three processes in the water cycle.", "Evaporation, condensation and precipitation"),
        ("Why can water dissolve so many ionic substances?", "Water molecules are polar, so they attract and surround ions"),
        ("Which gases cause acid rain?",
         "Sulfur dioxide and nitrogen oxides (from burning fossil fuels) dissolving in rainwater"),
        ("What is the pH of pure water at 25 degrees Celsius?", "7"),
    ],
}

PHYSICS_QUESTIONS_G11_EXTRA = {
    "Geometrical Optics": [
        ("State the law of reflection.", "The angle of incidence equals the angle of reflection"),
        ("Light goes from air (n = 1.00) into glass (n = 1.5) at 30 degrees to the normal. Calculate the angle of refraction.",
         "19.47 degrees"),
        ("Calculate the critical angle for light going from glass (n = 1.5) into air.", "41.81 degrees"),
        ("Give one everyday use of total internal reflection.", "Optical fibres (e.g. internet cables, endoscopes)"),
    ],
    "2D and 3D Wavefronts": [
        ("State Huygens' principle.",
         "Every point on a wavefront is a source of secondary wavelets; the new wavefront is the line tangent to them"),
        ("What is diffraction?", "The spreading of a wave as it passes through an opening or around an obstacle"),
        ("How does making a slit narrower change the diffraction pattern?", "Narrower slit: more diffraction (wider central band)"),
        ("Two waves meet in phase. What kind of interference happens?", "Constructive interference (larger amplitude)"),
    ],
}

CHEM_QUESTIONS_G11 = {
    "Atomic Combinations and Molecular Structure": [
        ("What is the molecular shape of CH4?", "Tetrahedral"),
        ("What is the molecular shape of H2O?", "Bent (angular)"),
        ("What is a dative covalent (coordinate) bond?",
         "A covalent bond in which both shared electrons come from the same atom (e.g. in NH4+)"),
        ("Is CO2 a polar or a non-polar molecule? Explain.",
         "Non-polar: the C=O bonds are polar, but the molecule is linear and symmetrical, so the dipoles cancel"),
    ],
    "Intermolecular Forces": [
        ("Name the strongest intermolecular force between water molecules.", "Hydrogen bonds"),
        ("Which has the higher boiling point, H2O or H2S? Explain.",
         "H2O: it has hydrogen bonds, which are stronger than the forces between H2S molecules"),
        ("What type of intermolecular force acts between non-polar molecules?", "London (dispersion) forces"),
        ("How do stronger intermolecular forces affect a liquid's vapour pressure?", "The vapour pressure is lower"),
    ],
    "Ideal Gases": [
        ("A gas occupies 2 dm^3 at 100 kPa. Find its volume at 200 kPa at constant temperature.", "1 dm^3"),
        ("Convert 27 degrees Celsius to kelvin.", "300 K"),
        ("A gas at 300 K has a volume of 3 dm^3. Find its volume at 600 K at constant pressure.", "6 dm^3"),
        ("How many moles of gas are in 4.48 dm^3 at STP?", "0.2 mol"),
    ],
    "Quantitative Aspects of Chemical Change": [
        ("Calculate the percentage of carbon in CO2 (C = 12, O = 16).", "27.27%"),
        ("N2 + 3H2 -> 2NH3. How many moles of NH3 form from 6 mol of H2 (N2 in excess)?", "4 mol"),
        ("A compound is 40% C, 6.7% H and 53.3% O by mass. Find its empirical formula.", "CH2O"),
        ("2 g of H2 reacts with 32 g of O2 (2H2 + O2 -> 2H2O). Which reactant is limiting?",
         "H2 (1 mol of H2 needs only 0.5 mol of the 1 mol O2)"),
    ],
    "Energy and Chemical Change": [
        ("Is the enthalpy change (delta H) positive or negative for an exothermic reaction?", "Negative"),
        ("What is activation energy?", "The minimum energy needed for a reaction to take place"),
        ("Is photosynthesis endothermic or exothermic?", "Endothermic"),
        ("What does a catalyst do to the activation energy?", "Lowers it, by providing an alternative pathway"),
    ],
    "Acids and Bases": [
        ("Define a base according to Lowry-Bronsted.", "A proton (H+) acceptor"),
        ("What are the products of HCl + NaOH?", "NaCl + H2O (a salt and water)"),
        ("What is an amphiprotic (amphoteric) substance? Give an example.",
         "A substance that can act as an acid or a base, e.g. water or HCO3-"),
        ("Name the conjugate base of HNO3.", "NO3- (the nitrate ion)"),
    ],
    "Redox Reactions": [
        ("Oxidation is the ... of electrons.", "loss"),
        ("What is the oxidation number of Mn in KMnO4?", "+7"),
        ("In Zn + Cu2+ -> Zn2+ + Cu, which substance is the reducing agent?", "Zn"),
        ("What is the oxidation number of oxygen in H2O2?", "-1"),
    ],
    "The Lithosphere": [
        ("What is an ore?", "Rock or a mineral from which a metal can be extracted at a profit"),
        ("Name the main ore of iron.", "Haematite (Fe2O3)"),
        ("Which chemical is used to dissolve gold out of crushed ore?", "A cyanide solution (e.g. sodium cyanide)"),
        ("Name one environmental impact of mining.", "E.g. acid mine drainage, land degradation, dust or water pollution"),
    ],
}

CHEM_QUESTIONS_G12 = {
    "Organic Molecules": [
        ("Give the IUPAC name of CH3CH2OH.", "Ethanol"),
        ("Give the general formula of the alkanes.", "CnH2n+2"),
        ("What is the IUPAC name of CH3COOH?", "Ethanoic acid"),
        ("What type of reaction makes an ester from an alcohol and a carboxylic acid?", "Esterification (condensation)"),
    ],
    "Rate and Extent of Reaction": [
        ("Name two factors that increase the rate of a reaction.",
         "Any two: higher temperature, higher concentration, larger surface area, a catalyst"),
        ("Use the collision theory to explain why a higher temperature increases the rate.",
         "Particles move faster, so more of them have energy above the activation energy: more effective collisions per second"),
        ("50 cm^3 of gas is produced in 25 s. Calculate the average rate of reaction.", "2 cm^3/s"),
        ("Does a catalyst change the yield of a reaction?", "No, it only changes the rate"),
    ],
    "Chemical Equilibrium": [
        ("Write the Kc expression for N2 + 3H2 <=> 2NH3.", "Kc = [NH3]^2 / ([N2][H2]^3)"),
        ("State Le Chatelier's principle.",
         "When an equilibrium is disturbed, the system shifts in the direction that opposes the disturbance"),
        ("The forward reaction is exothermic. What happens to Kc when the temperature increases?", "Kc decreases"),
        ("For N2 + 3H2 <=> 2NH3, which way does the equilibrium shift if the pressure increases?",
         "Forward (to the side with fewer moles of gas)"),
    ],
    "Acids and Bases": [
        ("Calculate the pH of 0.01 mol/dm^3 HCl.", "pH = 2"),
        ("Calculate the pH of 0.001 mol/dm^3 NaOH at 25 degrees Celsius.", "pH = 11"),
        ("What is the difference between a strong acid and a weak acid?",
         "A strong acid ionises completely in water; a weak acid ionises only partly"),
        ("25 cm^3 of 0.1 mol/dm^3 NaOH is neutralised by 0.1 mol/dm^3 HCl. What volume of HCl is needed?", "25 cm^3"),
    ],
    "Electrochemical Reactions": [
        ("In a galvanic cell, at which electrode does oxidation take place?", "The anode"),
        ("Calculate the emf of a Zn-Cu cell (E Cu2+/Cu = +0.34 V, E Zn2+/Zn = -0.76 V).", "1.10 V"),
        ("What does the salt bridge do?", "Completes the circuit and keeps the solutions electrically neutral"),
        ("What energy conversion takes place in an electrolytic cell?", "Electrical energy to chemical energy"),
    ],
    "The Chemical Industry": [
        ("A fertiliser bag says 3:2:1 (25). What does this mean?",
         "N:P:K in the ratio 3:2:1, and 25% of the mass is these nutrients"),
        ("Name the industrial process that makes ammonia.", "The Haber process"),
        ("Name the industrial process that makes nitric acid.", "The Ostwald process"),
        ("Name the three primary nutrients that fertilisers supply.", "Nitrogen, phosphorus and potassium (N, P, K)"),
    ],
}
