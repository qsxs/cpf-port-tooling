package acceptance

import androidx.compose.runtime.Composable
import com.cheonjaeung.compose.grid.SimpleGridCells
import com.cheonjaeung.compose.grid.VerticalGrid

// 仅编译现有用法，不添加业务 UI 或设备运行夹具。
@Composable
fun GridConsumerProbe() {
    VerticalGrid(columns = SimpleGridCells.Fixed(2)) {}
}
