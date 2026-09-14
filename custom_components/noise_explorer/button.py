"""User-triggered watch commands. No commands run merely by creating entities."""

from homeassistant.components.button import ButtonEntity

from .const import BUTTONS
from .entity import NoiseEntity, discover_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(hass, entry, async_add_entities):
    discover_entities(
        entry,
        async_add_entities,
        lambda c, e, w: (
            NoiseButton(c, e, key, name, action) for key, (name, action) in BUTTONS.items()
        ),
    )


class NoiseButton(NoiseEntity, ButtonEntity):
    def __init__(self, coordinator, eid, key, name, action):
        super().__init__(coordinator, eid, key, name)
        self.action = action

    async def async_press(self):
        if self.action is None:
            await self.coordinator.async_request_refresh()
        else:
            await self.coordinator.async_command(
                self.eid, self.action, {"Key": "1"} if self.action == 158 else None
            )
