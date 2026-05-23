"""
DKT Engine — Deep Knowledge Tracing (lightweight version).

Propagates P(L) updates from prerequisite skills to dependent skills via
the knowledge_graph table.

Coefficient: P(L_child) += DKT_COEFF * delta_P(L_parent)

A full production build would replace this with a trained LSTM/GRU network.
"""

DKT_COEFF = 0.15   # tunable propagation coefficient


def propagate(
    db,
    student_id: str,
    updated_skill_id: str,
    old_p: float,
    new_p: float,
):
    """
    When a skill's P(L) changes, propagate a fraction of that delta to all
    child skills (skills that list updated_skill_id as a prerequisite).
    """
    from app.models import KnowledgeGraph, BKTState
    from datetime import datetime

    delta = new_p - old_p
    if abs(delta) < 0.001:
        return  # negligible change — skip

    # Find all skills that have updated_skill_id as a prerequisite (children)
    children = (
        db.query(KnowledgeGraph)
        .filter(KnowledgeGraph.parent_skill_id == updated_skill_id)
        .all()
    )

    for edge in children:
        child_id = edge.child_skill_id
        state = (
            db.query(BKTState)
            .filter(
                BKTState.student_id == student_id,
                BKTState.skill_id == child_id,
            )
            .first()
        )

        if state is None:
            # Create a new BKT state for the child with partial knowledge
            state = BKTState(
                student_id=student_id,
                skill_id=child_id,
                p_mastery=max(0.10, 0.10 + DKT_COEFF * delta),
                attempts=0,
                last_updated=datetime.utcnow(),
            )
            db.add(state)
        else:
            new_child_p = max(0.001, min(0.999, state.p_mastery + DKT_COEFF * delta))
            state.p_mastery = new_child_p
            state.last_updated = datetime.utcnow()

    db.commit()
